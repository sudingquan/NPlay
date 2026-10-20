#!/usr/bin/env python3
"""Provision release secrets with GitHub CLI; never print credential values."""

import argparse
import base64
import io
import json
import os
from pathlib import Path
import re
import secrets
import shutil
import subprocess
import zipfile


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repository', default='sudingquan/NPlay')
    parser.add_argument('--auth-apk', type=Path, required=True,
                        help='Standalone APK, or a ZIP containing one non-rollback APK')
    parser.add_argument('--signing-dir', type=Path,
                        default=Path.home() / '.config' / 'nplay-release',
                        help='Persistent private folder to back up; reused for every release')
    args = parser.parse_args()
    if not re.fullmatch(r'[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+', args.repository):
        parser.error('Expected repository owner/name')
    if not shutil.which('gh'):
        raise SystemExit('Install GitHub CLI first: https://cli.github.com/')
    if subprocess.run(['gh', 'auth', 'status'], capture_output=True).returncode:
        raise SystemExit('Sign in first with: gh auth login')
    check = subprocess.run(['gh', 'repo', 'view', args.repository, '--json', 'nameWithOwner'],
                           capture_output=True, text=True)
    if check.returncode:
        raise SystemExit('GitHub CLI cannot access the requested repository.')

    # Accept the diagnostic ZIP previously used for the head unit as well as a bare APK.
    with zipfile.ZipFile(args.auth_apk.expanduser()) as source:
        if 'assets/offline-mfi/identity.pk8' in source.namelist():
            apk_data = None
        else:
            candidates = [name for name in source.namelist()
                          if name.endswith('.apk') and 'rollback' not in name.lower()]
            if len(candidates) != 1:
                raise SystemExit('Select a standalone APK or a ZIP containing exactly one non-rollback APK.')
            apk_data = source.read(candidates[0])
        if apk_data is None:
            auth = {name: source.read('assets/offline-mfi/' + name)
                    for name in ('identity.pk8', 'certificate.p7b')}
        else:
            with zipfile.ZipFile(io.BytesIO(apk_data)) as apk:
                auth = {name: apk.read('assets/offline-mfi/' + name)
                        for name in ('identity.pk8', 'certificate.p7b')}
    if not all(auth.values()):
        raise SystemExit('The selected APK contains an empty authentication file.')

    root = args.signing_dir.expanduser().resolve()
    repo = Path(__file__).resolve().parents[1]
    if root == root.parent or root == Path.home().resolve():
        raise SystemExit('Choose a dedicated folder for the signing backup.')
    if root == repo or repo in root.parents:
        raise SystemExit('Choose a signing directory outside the source repository.')
    root.mkdir(mode=0o700, parents=True, exist_ok=True)
    root.chmod(0o700)
    keystore = root / 'release.p12'
    config = root / 'credentials.json'
    if keystore.exists() != config.exists():
        raise SystemExit('Incomplete signing backup: restore both release.p12 and credentials.json; do not rotate the key.')
    if not keystore.exists():
        if not shutil.which('keytool'):
            raise SystemExit('Install a Java JDK providing keytool, then run this command again.')
        password = secrets.token_urlsafe(32)
        values = dict(password=password, alias='nplay')
        key_env = dict(os.environ, NPLAY_SETUP_PASSWORD=password)
        os.umask(0o077)
        result = subprocess.run([
            'keytool', '-genkeypair', '-storetype', 'PKCS12', '-keystore', str(keystore),
            '-storepass:env', 'NPLAY_SETUP_PASSWORD', '-keypass:env', 'NPLAY_SETUP_PASSWORD',
            '-alias', values['alias'], '-keyalg', 'RSA', '-keysize', '3072',
            '-validity', '10000', '-dname', 'CN=NPlay Release', '-noprompt',
        ], env=key_env, capture_output=True)
        if result.returncode:
            raise SystemExit('keytool could not generate the signing key. No secrets were uploaded.')
        config.write_text(json.dumps(values) + '\n')
        config.chmod(0o600)
        keystore.chmod(0o600)
    values = json.loads(config.read_text())
    contents = {
        'ANDROID_KEYSTORE_BASE64': base64.b64encode(keystore.read_bytes()).decode(),
        'ANDROID_KEYSTORE_PASSWORD': values['password'],
        'ANDROID_KEY_ALIAS': values['alias'],
        'ANDROID_KEY_PASSWORD': values['password'],
        'DIPLAY_IDENTITY_BASE64': base64.b64encode(auth['identity.pk8']).decode(),
        'DIPLAY_CERTIFICATE_BASE64': base64.b64encode(auth['certificate.p7b']).decode(),
    }
    if any(len(value.encode()) >= 48 * 1024 for value in contents.values()):
        raise SystemExit('A credential exceeds the GitHub secret size limit; nothing was uploaded.')
    for name, value in contents.items():
        result = subprocess.run(['gh', 'secret', 'set', name, '--repo', args.repository],
                                input=value.encode(), capture_output=True)
        if result.returncode:
            raise SystemExit(f'Could not save {name}. Check GitHub CLI permissions and rerun with the same signing folder.')
        print('Saved ' + name)
    print(f'Ready. Back up this private signing folder: {root}')
    print(f'Run the release workflow: https://github.com/{args.repository}/actions/workflows/release.yml')


if __name__ == '__main__':
    main()
