#!/usr/bin/env python3
"""Bind reviewed release bytes and successful source checks to a dispatch plan."""
import hashlib
import json
import os
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MANIFEST_DIGEST = '4f5bb96e1fe07f7b56cfe124206ed85c4e59b9715b3b4e18b3054d890dd1ad32'
VERIFICATION_DIGEST = '369f1b94a0e25e8c2e0f8bfddb15752a5df2772df549ecf2814091c34c480fae'


def digest(raw):
    return 'sha256:' + hashlib.sha256(raw).hexdigest()


def encode(value):
    return (json.dumps(value, sort_keys=True, separators=(',', ':')) + '\n').encode()


def assemble(manifest_raw, verification_raw, test_receipt, commit, destinations):
    if not re.fullmatch('[0-9a-f]{40}', commit):
        raise ValueError('dispatch commit must be an immutable SHA')
    if digest(manifest_raw) != 'sha256:' + MANIFEST_DIGEST:
        raise ValueError('release manifest differs from reviewed signed bytes')
    if digest(verification_raw) != 'sha256:' + VERIFICATION_DIGEST:
        raise ValueError('verification receipt differs from reviewed public evidence')
    manifest = json.loads(manifest_raw)
    verification = json.loads(verification_raw)
    statement = verification[0]['verificationResult']['statement']
    if statement['subject'] != [{'name': 'release-manifest.json', 'digest': {'sha256': MANIFEST_DIGEST}}]:
        raise ValueError('verification receipt subject does not bind the release manifest')
    if test_receipt.get('dispatchCommit') != commit or test_receipt.get('result') != 'passed':
        raise ValueError('source test receipt must bind the successful dispatch checkout')
    if set(destinations) != {item['variant'] for item in manifest['images']}:
        raise ValueError('destinations must cover exactly the signed release variants')
    inventory = {
        'schemaVersion': 1,
        'scope': 'signed-release-sbom-references; not a license clearance or full SBOM inventory',
        'sourceManifestDigest': digest(manifest_raw),
        'sourceVerificationReceiptDigest': digest(verification_raw),
        'images': [{key: item[key] for key in ('variant', 'repository', 'indexDigest', 'sbom', 'provenance')}
                   for item in manifest['images']],
    }
    images = []
    for item in manifest['images']:
        target = destinations[item['variant']]
        if not isinstance(target, str) or not re.fullmatch(r'[a-z0-9.-]+(/[a-z0-9]+([._-][a-z0-9]+)*)+:0\.2\.1', target):
            raise ValueError('destination must identify the released version')
        images.append({'source': item['repository'] + '@' + item['indexDigest'],
                       'destination': target, 'digest': item['indexDigest']})
    plan = {
        'schemaVersion': 1,
        'sourceRepository': 'https://github.com/' + manifest['source']['repository'],
        'sourceCommit': manifest['source']['commit'],
        'dispatchCommit': commit,
        'version': manifest['releaseVersion'],
        'sourceManifestDigest': digest(manifest_raw),
        'licenseInventoryDigest': digest(encode(inventory)),
        'testReceiptDigest': digest(encode(test_receipt)),
        'images': images,
    }
    return plan, inventory


def main():
    output = os.environ.get('VERJSON_PRODUCER_PLAN', '.verjson-ci/producer-plan.json')
    if output != '.verjson-ci/producer-plan.json':
        raise ValueError('producer plan output must use the fixed artifact path')
    commit = os.environ.get('VERJSON_PRODUCER_DISPATCH_COMMIT', '')
    evidence = ROOT / '.verjson-ci/producer-evidence'
    manifest_raw = (ROOT / 'RELEASES/containers/v0.2.1.json').read_bytes()
    verification_raw = (ROOT / '.verjson/release-v0.2.1-verification.json').read_bytes()
    receipt = json.loads((evidence / 'test-receipt.json').read_bytes())
    destinations = json.loads((ROOT / '.verjson/producer-destinations.json').read_bytes())
    plan, inventory = assemble(manifest_raw, verification_raw, receipt, commit, destinations)
    (evidence / 'source-manifest.json').write_bytes(manifest_raw)
    (evidence / 'license-inventory.json').write_bytes(encode(inventory))
    (ROOT / output).write_bytes(encode(plan))


if __name__ == '__main__':
    main()
