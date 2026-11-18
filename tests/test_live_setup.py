"""Tests for the owner-run typed live setup wizard. No provider access."""
import json
import os
import stat

import pytest

from aether.devops.lifecycle_design import design_lifecycle_change
from aether.devops.live_setup import collect_plan, setup_live_cloud, write_opt_in

EC2 = {
    "account_id": "123456789012",
    "partition": "aws",
    "region": "ap-south-1",
    "profile": "dev",
    "instance_id": "i-0123456789abcdef0",
}
K8S = {
    "context": "prod-cluster",
    "cluster_uid": "9c0a1b2c-1234-4abc-8def-001122334455",
    "cluster_ca_sha256": "a" * 64,
    "namespace": "web",
    "deployment": "api",
    "deployment_uid": "b1234567-89ab-4cde-8f01-23456789abcd",
    "resource_version": "123456",
    "current_replicas": "2",
    "target_replicas": "4",
    "hpa_state": "absent",
}


def test_collect_plan_ec2_start_digest_matches_design():
    built = collect_plan("ec2_start", dict(EC2))
    assert built["plan"]["expected_state"] == "stopped"
    proposal = design_lifecycle_change(built["plan_json"])
    assert proposal["proposal_sha256"] == built["digest"]
    assert built["warnings"]


def test_collect_plan_ec2_stop_expected_state():
    built = collect_plan("ec2_stop", dict(EC2))
    assert built["plan"]["expected_state"] == "running"


def test_collect_plan_k8s_coerces_replica_strings():
    built = collect_plan("k8s_scale", dict(K8S))
    assert built["plan"]["current_replicas"] == 2
    assert built["plan"]["target_replicas"] == 4
    assert design_lifecycle_change(built["plan_json"])["proposal_sha256"] == built["digest"]


def test_collect_plan_refuses_github_dispatch():
    with pytest.raises(ValueError):
        collect_plan("github_dispatch", {})


def test_collect_plan_refuses_bad_instance_id():
    bad = dict(EC2, instance_id="i-notreal")
    with pytest.raises(ValueError):
        collect_plan("ec2_start", bad)


def test_collect_plan_refuses_extra_fields():
    with pytest.raises(ValueError):
        collect_plan("ec2_start", dict(EC2, arn="arn:aws:ec2:::x"))


def test_collect_plan_refuses_partition_region_mismatch():
    with pytest.raises(ValueError):
        collect_plan("ec2_start", dict(EC2, partition="aws-cn"))


def test_write_opt_in_owner_only_and_no_overwrite(tmp_path, monkeypatch):
    monkeypatch.setenv("AETHER_LIVE_SETUP_DIR", str(tmp_path))
    built = collect_plan("ec2_start", dict(EC2))
    written = write_opt_in(tmp_path, "ab" * 16, built["digest"], built["plan_json"])
    env_text = open(written["env_file"]).read()
    assert "AETHER_ENABLE_TYPED_LIVE=I_REVIEWED_REAL_TARGETS" in env_text
    assert "AETHER_TYPED_CONNECTION_GENERATION=" + "ab" * 16 in env_text
    assert "AETHER_TYPED_ALLOWED_SCOPE_SHA256=" + built["digest"] in env_text
    assert json.loads(open(written["plan_file"]).read())["operation"] == "ec2_start"
    if os.name == "posix":
        assert stat.S_IMODE(os.stat(written["env_file"]).st_mode) == 0o600
        assert stat.S_IMODE(os.stat(written["plan_file"]).st_mode) == 0o600
    with pytest.raises(ValueError):
        write_opt_in(tmp_path, "cd" * 16, built["digest"], built["plan_json"])
    again = write_opt_in(tmp_path, "cd" * 16, built["digest"], built["plan_json"], replace=True)
    assert "cd" * 16 in open(again["env_file"]).read()


def test_write_opt_in_refuses_symlink(tmp_path):
    built = collect_plan("ec2_start", dict(EC2))
    target = tmp_path / "real.env"
    target.write_text("x")
    link = tmp_path / "typed-live.env"
    if hasattr(os, "symlink"):
        os.symlink(target, link)
        with pytest.raises(ValueError):
            write_opt_in(tmp_path, "ab" * 16, built["digest"], built["plan_json"])


def _scripted(responses):
    answers = iter(responses)

    def ask(prompt):
        return next(answers)

    return ask


def test_wizard_declined_start(tmp_path, monkeypatch):
    monkeypatch.setenv("AETHER_LIVE_SETUP_DIR", str(tmp_path))
    result = setup_live_cloud(_scripted([]), lambda prompt: False)
    assert result == {"completed": False, "reason": "owner_declined"}
    assert not (tmp_path / "typed-live.env").exists()


def test_wizard_phrase_mismatch_writes_nothing(tmp_path, monkeypatch):
    monkeypatch.setenv("AETHER_LIVE_SETUP_DIR", str(tmp_path))
    responses = ["1", "", EC2["account_id"], EC2["partition"], "", EC2["region"], EC2["profile"], "", EC2["instance_id"], "", "", "", "wrong phrase"]
    result = setup_live_cloud(_scripted(responses), lambda prompt: True)
    assert result == {"completed": False, "reason": "phrase_not_confirmed"}
    assert not (tmp_path / "typed-live.env").exists()


def test_wizard_full_ec2_flow(tmp_path, monkeypatch):
    monkeypatch.setenv("AETHER_LIVE_SETUP_DIR", str(tmp_path))
    # choice, then fields in EC2_FIELDS order (Enter for helper prompts), 3 warnings, phrase
    responses = ["1", "", EC2["account_id"], EC2["partition"], "", EC2["region"], EC2["profile"], "", EC2["instance_id"], "", "", "", "I REVIEWED REAL TARGETS AND COSTS"]
    result = setup_live_cloud(_scripted(responses), lambda prompt: True)
    assert result["completed"] is True
    assert result["operation"] == "ec2_start"
    env_text = open(result["env_file"]).read()
    assert result["digest"] in env_text
    assert any("prepare" in step for step in result["steps"])
    assert any("revoke" in step for step in result["steps"])


def test_wizard_full_k8s_flow(tmp_path, monkeypatch):
    monkeypatch.setenv("AETHER_LIVE_SETUP_DIR", str(tmp_path))
    # K8S_FIELDS order with helper Enter for context, cluster_uid, cluster_ca_sha256,
    # deployment_uid, resource_version, current_replicas, hpa_state
    responses = [
        "3",
        "", K8S["context"],
        "", K8S["cluster_uid"],
        "", K8S["cluster_ca_sha256"],
        K8S["namespace"],
        K8S["deployment"],
        "", K8S["deployment_uid"],
        "", K8S["resource_version"],
        "", K8S["current_replicas"],
        K8S["target_replicas"],
        "", K8S["hpa_state"],
        "", "", "",
        "I REVIEWED REAL TARGETS AND COSTS",
    ]
    result = setup_live_cloud(_scripted(responses), lambda prompt: True)
    assert result["completed"] is True
    assert json.loads(open(result["plan_file"]).read())["operation"] == "k8s_scale"


def test_wizard_replace_flow(tmp_path, monkeypatch):
    monkeypatch.setenv("AETHER_LIVE_SETUP_DIR", str(tmp_path))
    responses = ["1", "", EC2["account_id"], EC2["partition"], "", EC2["region"], EC2["profile"], "", EC2["instance_id"], "", "", "", "I REVIEWED REAL TARGETS AND COSTS"]
    assert setup_live_cloud(_scripted(list(responses)), lambda prompt: True)["completed"] is True
    # Second run: existing file -> replace prompt; decline -> nothing overwritten
    before = open(tmp_path / "typed-live.env").read()
    confirms = iter([True, False])
    result = setup_live_cloud(_scripted(list(responses)), lambda prompt: next(confirms))
    assert result == {"completed": False, "reason": "replace_declined"}
    assert open(tmp_path / "typed-live.env").read() == before
