# AETHER direct setup files

Built from source commit `bdb5ac93dbe4f49da75789c00d77c432494b99ae`.
Verified successful build: https://github.com/Ashokkunchala/AETHER/actions/runs/44003335873

- `AETHER-Setup.exe`: unsigned Windows setup launcher, not an offline/standalone assistant. Requires Windows10/11, Python3.11+ and internet. Inspect the included PowerShell payload and checksums before running. It asks separately to download the exact source and install packages into a NEW folder. No old installation overwrite, startup registration, provider launch or phone effects.
- `AETHER-Android.apk`: debug/test Android APK. Installing/updating is an owner action. Do not uninstall/erase an existing app to force a signature-conflicting update. Secure same-backend HTTPS, pairing and reviewed permissions still need setup and actual device acceptance.
- `install-aether-reviewed.ps1`: the readable Windows payload embedded in the executable.
- `SHA256SUMS.txt` and `SOURCE-COMMIT.txt`: exact binary integrity/source references. These are not a code signature or safety guarantee.

Download an individual file with GitHub's Download raw file button, not the webpage saved as HTML. The repository has the files directly; no Actions artifact ZIP is required. Use the raw links supplied with the completion report.

No public Release was created. These files have the SAME visibility as this repository. No user device was installed, started, paired or changed by publishing them. Do not bypass unexplained antivirus/SmartScreen/TLS warnings. This is tested source/build output, not proof all AETHER abilities work on your devices.

Full owner-run guide: [installation downloads](../docs/INSTALLABLE-FILES.md).
