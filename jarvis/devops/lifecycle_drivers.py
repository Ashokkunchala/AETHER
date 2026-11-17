"""Typed SDK drivers. Constructed only behind the disabled local runtime gate.

No subprocess, arbitrary argv, write retries, shell or deployment fallback.
SDKs are optional extras; no installation is performed at runtime.
"""
from __future__ import annotations

import hashlib
import os


class LiveDrivers:
    def __init__(self):
        self._drivers = {}

    def _driver(self, plan):
        operation = plan["operation"]
        key = "ec2" if operation.startswith("ec2_") else operation
        if key not in self._drivers:
            if key == "ec2":
                import boto3
                from botocore.config import Config
                session = boto3.Session(profile_name=plan["profile"], region_name=plan["region"])
                # CLI credential processes could execute unreviewed machine commands.
                profiles = session._session.full_config.get("profiles", {})
                if any(config.get("credential_process") for config in profiles.values()):
                    raise ValueError("External credential processes are not supported by this typed adapter.")
                config = Config(retries={"total_max_attempts": 1}, connect_timeout=5, read_timeout=20, ignore_configured_endpoint_urls=True)
                ec2 = session.client("ec2", config=config)
                sts = session.client("sts", config=config)
                self._drivers[key] = EC2Driver(ec2, sts)
            elif key == "k8s_scale":
                from kubernetes import client, config
                import yaml
                paths = os.getenv("KUBECONFIG", str(__import__("pathlib").Path.home() / ".kube" / "config")).split(os.pathsep)
                for path in paths:
                    with open(path, encoding="utf-8") as stream:
                        raw = yaml.safe_load(stream)
                    if not isinstance(raw, dict) or any(user.get("user", {}).get("exec") or user.get("user", {}).get("auth-provider") for user in raw.get("users", [])):
                        raise ValueError("Exec/auth-provider credential plugins are not supported; no machine-command fallback.")
                    if any(c.get("cluster", {}).get("insecure-skip-tls-verify") for c in raw.get("clusters", [])):
                        raise ValueError("TLS verification must remain enabled.")
                api = config.new_client_from_config(context=plan["context"])
                if not api.configuration.verify_ssl or not api.configuration.host.startswith("https://"):
                    raise ValueError("Verified HTTPS Kubernetes endpoint required.")
                api.rest_client.pool_manager.connection_pool_kw["retries"] = False
                ca = api.configuration.ssl_ca_cert
                if not ca:
                    raise ValueError("Explicit reviewed cluster CA file required.")
                with open(ca, "rb") as stream:
                    raw_ca = stream.read(1_048_577)
                    if not 1 <= len(raw_ca) <= 1_048_576:
                        raise ValueError("Bounded cluster CA file required.")
                    fingerprint = hashlib.sha256(raw_ca).hexdigest()
                self._drivers[key] = KubernetesScaleDriver(client.AppsV1Api(api), client.CoreV1Api(api), client.AutoscalingV2Api(api), fingerprint)
            else:
                # GitHub dispatch takes a mutable branch/tag ref, not an immutable
                # commit precondition. Never silently bypass the approved artifact.
                raise ValueError("Live GitHub dispatch is blocked until an immutable-ref and complete workflow-effect review strategy is approved. Typed injected transport is testable, not enabled for live dispatch.")
        return self._drivers[key]

    def preflight(self, plan):
        return self._driver(plan).preflight(plan)

    def dispatch(self, plan, guard):
        return self._driver(plan).dispatch(plan, guard)

    def verify(self, plan, receipt):
        return self._driver(plan).verify(plan, receipt)


class EC2Driver:
    def __init__(self, ec2, sts):
        self.ec2, self.sts = ec2, sts

    def _read(self, plan):
        identity = self.sts.get_caller_identity()
        if identity.get("Account") != plan["account_id"] or not identity.get("Arn", "").startswith("arn:" + plan["partition"] + ":"):
            raise ValueError("Live AWS identity mismatch.")
        if self.ec2.meta.region_name != plan["region"]:
            raise ValueError("Live AWS region mismatch.")
        response = self.ec2.describe_instances(InstanceIds=[plan["instance_id"]])
        instances = [item for group in response.get("Reservations", []) for item in group.get("Instances", [])]
        if len(instances) != 1 or instances[0].get("InstanceId") != plan["instance_id"]:
            raise ValueError("Exact EC2 target unavailable/ambiguous.")
        return instances[0], identity

    def preflight(self, plan):
        instance, identity = self._read(plan)
        if instance.get("RootDeviceType") != "ebs" or instance.get("State", {}).get("Name") != plan["expected_state"]:
            raise ValueError("Unsupported root or current state; no force/no-op fallback.")
        if instance.get("InstanceLifecycle") in ("spot", "scheduled"):
            raise ValueError("Spot/scheduled lifecycle is not supported by this adapter.")
        if plan["operation"] == "ec2_stop":
            protection = self.ec2.describe_instance_attribute(InstanceId=plan["instance_id"], Attribute="disableApiStop")
            if protection.get("DisableApiStop", {}).get("Value") is not False:
                raise ValueError("Stop protection missing, unknown or enabled.")
        return {"target_verified": True, "account": identity["Account"], "principal_digest": hashlib.sha256(identity["Arn"].encode()).hexdigest(),
                "region": plan["region"], "instance": instance["InstanceId"], "state": instance["State"]["Name"],
                "root": "ebs", "type": instance.get("InstanceType"), "launch_time": str(instance.get("LaunchTime", "")),
                "block_devices_digest": hashlib.sha256(str(instance.get("BlockDeviceMappings", [])).encode()).hexdigest(),
                "cost_known": False, "data_loss_and_outage_review_required": True}

    def dispatch(self, plan, guard):
        guard()
        if plan["operation"] == "ec2_start":
            response = self.ec2.start_instances(InstanceIds=[plan["instance_id"]])
            items = response.get("StartingInstances", [])
        elif plan["operation"] == "ec2_stop":
            response = self.ec2.stop_instances(InstanceIds=[plan["instance_id"]], Force=False, Hibernate=False, SkipOsShutdown=False)
            items = response.get("StoppingInstances", [])
        else:
            raise ValueError("Not an EC2 start/stop proposal.")
        if len(items) != 1 or items[0].get("InstanceId") != plan["instance_id"]:
            raise ValueError("Ambiguous EC2 acceptance; reconcile, never retry.")
        return {"accepted": True, "instance": plan["instance_id"]}

    def verify(self, plan, receipt):
        instance, _ = self._read(plan)
        expected = "running" if plan["operation"] == "ec2_start" else "stopped"
        return instance.get("State", {}).get("Name") == expected


class KubernetesScaleDriver:
    def __init__(self, apps, core, autoscaling, ca_digest):
        self.apps, self.core, self.autoscaling, self.ca = apps, core, autoscaling, ca_digest

    def _read(self, plan):
        kw = {"_request_timeout": (5, 20)}
        if self.ca != plan["cluster_ca_sha256"]:
            raise ValueError("Cluster CA mismatch.")
        # Documented adapter convention: cluster_uid is the kube-system namespace UID.
        identity = self.core.read_namespace("kube-system", **kw)
        if str(identity.metadata.uid) != plan["cluster_uid"]:
            raise ValueError("Cluster identity mismatch.")
        self.core.read_namespace(plan["namespace"], **kw)
        deployment = self.apps.read_namespaced_deployment(plan["deployment"], plan["namespace"], **kw)
        if str(deployment.metadata.uid) != plan["deployment_uid"]:
            raise ValueError("Deployment UID mismatch.")
        return deployment

    def preflight(self, plan):
        deployment = self._read(plan)
        if plan["hpa_state"] != "absent":
            raise ValueError("HPA present/unknown blocks manual scaling.")
        response = self.autoscaling.list_namespaced_horizontal_pod_autoscaler(plan["namespace"], _request_timeout=(5, 20))
        if getattr(response.metadata, "_continue", None):
            raise ValueError("Incomplete autoscaler inventory.")
        if any(item.spec.scale_target_ref.kind == "Deployment" and item.spec.scale_target_ref.name == plan["deployment"] for item in response.items):
            raise ValueError("Live HPA owns this Deployment.")
        version, current = str(deployment.metadata.resource_version), deployment.spec.replicas
        if version != plan["resource_version"] or current != plan["current_replicas"]:
            raise ValueError("Live version/replica drift.")
        return {"target_verified": True, "cluster": plan["cluster_uid"], "ca": self.ca,
                "namespace": plan["namespace"], "deployment_uid": plan["deployment_uid"], "resource_version": version,
                "current_replicas": current, "hpa": "absent", "cost_known": False, "quota_and_other_controller_review_required": True}

    def dispatch(self, plan, guard):
        body = {"apiVersion": "autoscaling/v1", "kind": "Scale", "metadata": {"name": plan["deployment"], "namespace": plan["namespace"], "uid": plan["deployment_uid"], "resourceVersion": plan["resource_version"]}, "spec": {"replicas": plan["target_replicas"]}}
        guard()
        result = self.apps.replace_namespaced_deployment_scale(plan["deployment"], plan["namespace"], body, _request_timeout=(5, 20))
        if str(result.metadata.uid) != plan["deployment_uid"] or result.spec.replicas != plan["target_replicas"]:
            raise ValueError("Scale acceptance target mismatch.")
        return {"accepted": True, "deployment_uid": plan["deployment_uid"]}

    def verify(self, plan, receipt):
        deployment = self._read(plan)
        return deployment.spec.replicas == plan["target_replicas"]


class GitHubDispatchDriver:
    """Injected typed transport contract, not wired to live HTTP until ref-race policy exists."""
    def __init__(self, transport):
        self.transport = transport

    def preflight(self, plan):
        evidence = self.transport.read_reviewed_workflow(plan)
        required = {"repository_id": plan["repository_id"], "workflow_id": plan["workflow_id"], "commit": plan["resolved_commit_sha"], "blob": plan["workflow_blob_sha"], "no_inputs_or_defaults": True, "effects_reviewed": True, "ref_pinned": True}
        if evidence != required:
            raise ValueError("Workflow identity/artifact/default-input/effect/ref-pinning review incomplete.")
        return {"target_verified": True, **evidence}

    def dispatch(self, plan, guard):
        guard()
        result = self.transport.dispatch_no_inputs(plan["repository_id"], plan["workflow_id"], plan["ref"])
        if type(result.get("run_id")) is not int or result["run_id"] <= 0:
            raise ValueError("No unambiguous returned run; reconcile without retry.")
        return {"run_id": result["run_id"], "accepted": True}

    def verify(self, plan, receipt):
        if not receipt or type(receipt.get("run_id")) is not int:
            return False
        run = self.transport.read_run(plan["repository_id"], receipt["run_id"])
        return run.get("workflow_id") == plan["workflow_id"] and run.get("head_sha") == plan["resolved_commit_sha"] and run.get("status") == "completed" and run.get("conclusion") == "success"
