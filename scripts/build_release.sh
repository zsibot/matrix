#!/usr/bin/env bash
# Build local Release assets. This script never uploads or publishes anything.
set -euo pipefail
if [[ ${1:-} == --help || $# != 2 ]]; then
    printf 'Usage: %s RUNTIME_DIRECTORY OUTPUT_DIRECTORY\n' "$0"
    printf 'Creates a full tar.gz under full/, split assets under github/, and SHA-256 manifests.\n'
    printf 'PART_BYTES defaults to 1900000000; values must be below 2000000000. GZIP_LEVEL defaults to 6 (1..9).\n'
    [[ ${1:-} == --help ]] && exit 0
    exit 2
fi
for command in tar gzip split sha256sum python3 realpath; do
    command -v "$command" >/dev/null || { printf 'Missing command: %s\n' "$command" >&2; exit 1; }
done
gzip_level=${GZIP_LEVEL:-6}
[[ $gzip_level =~ ^[1-9]$ ]] || { printf 'GZIP_LEVEL must be 1..9.\n' >&2; exit 2; }
part_bytes=${PART_BYTES:-1900000000}
[[ $part_bytes =~ ^[1-9][0-9]{0,9}$ ]] && (( part_bytes < 2000000000 )) || {
    printf 'PART_BYTES must be a positive integer below 2000000000.\n' >&2; exit 2;
}
runtime=$(realpath -- "$1")
output=$(realpath -m -- "$2")
name=$(basename -- "$runtime")
[[ $name =~ ^MATRiX_v[0-9]+\.[0-9]+\.[0-9]+$ ]] || { printf 'Expected MATRiX_vX.Y.Z runtime directory.\n' >&2; exit 2; }
[[ -f $runtime/UeSim.sh && -f $runtime/UeSim/Binaries/Linux/UeSim ]] || { printf 'Incomplete runtime directory.\n' >&2; exit 1; }
[[ $output != "$runtime" && $output != "$runtime/"* ]] || { printf 'Output must be outside the runtime.\n' >&2; exit 2; }
[[ ! -e $output ]] || { printf 'Output already exists; choose a new directory: %s\n' "$output" >&2; exit 1; }
parent=$(dirname -- "$output")
mkdir -p -- "$parent"
work=$(mktemp -d "$parent/.matrix-release.XXXXXXXX")
trap 'rm -rf -- "$work"' EXIT
mkdir -p "$work/full" "$work/github"
archive="$name.tar.gz"
printf 'Compressing %s (runtime and debug files retained; local logs/config/cache excluded)...\n' "$name"
# Do not distribute previous runs or development environments. Saved/DLCs is retained.
tar -C "$(dirname -- "$runtime")" \
    --exclude="$name/UeSim/Content/model/xxg" \
    --exclude="$name/UeSim/Saved/Logs" \
    --exclude="$name/UeSim/Saved/Config" \
    --exclude="$name/UeSim/Saved/Crashes" \
    --exclude="$name/UeSim/Saved/Profiling" \
    --exclude="$name/Saved" \
    --exclude='.venv' --exclude='__pycache__' --exclude='*.pyc' \
    -cf - -- "$name" | gzip "-$gzip_level" > "$work/full/$archive"
printf 'Checking compressed stream and archive listing...\n'
tar -tzf "$work/full/$archive" > "$work/archive-files.txt"
(
    cd "$work/full"
    sha256sum "$archive" > SHA256SUMS-full
)
printf 'Splitting into parts smaller than 2 GB...\n'
split -b "$part_bytes" -d --numeric-suffixes=1 -a 3 "$work/full/$archive" "$work/github/$archive.part-"
(
    cd "$work/github"
    sha256sum "$archive".part-* > SHA256SUMS
    sha256sum -c SHA256SUMS
)
cp "$work/full/SHA256SUMS-full" "$work/github/SHA256SUMS-full"
python3 - "$work" "$archive" "$part_bytes" "$runtime" <<'PY'
import hashlib, json, pathlib, sys
root, archive, limit = pathlib.Path(sys.argv[1]), sys.argv[2], int(sys.argv[3])
parts = sorted((root/'github').glob(archive+'.part-*'))
combined = hashlib.sha256()
records = []
for part in parts:
    size = part.stat().st_size
    assert 0 < size <= limit < 2_000_000_000
    digest = hashlib.sha256()
    with part.open('rb') as stream:
        for block in iter(lambda: stream.read(8*1024*1024), b''):
            combined.update(block); digest.update(block)
    records.append({'name': part.name, 'size_bytes': size, 'sha256': digest.hexdigest()})
full_hash = (root/'full/SHA256SUMS-full').read_text().split()[0]
assert combined.hexdigest() == full_hash, 'Reassembled archive checksum mismatch'
manifest = {'archive': archive, 'archive_size_bytes': (root/'full'/archive).stat().st_size,
            'archive_sha256': full_hash, 'part_size_limit_bytes': limit, 'parts': records}
build_file = pathlib.Path(sys.argv[4]) / 'RELEASE_BUILD.json'
if build_file.is_file():
    manifest['runtime_build'] = json.loads(build_file.read_text())
(root/'github/release-manifest.json').write_text(json.dumps(manifest, indent=2)+'\n')
(root/'github/EXTRACT.md').write_text(
    '# MATRiX Linux Release\n\n'
    '下载本目录全部 `.part-*` 和 `SHA256SUMS`，放入同一目录并保留原名。\n'
    'Download every `.part-*` plus `SHA256SUMS` into one directory.\n'
    'Run in a directory containing only the parts of this release.\n\n'
    '```bash\nsha256sum -c SHA256SUMS && \\\n'
    f'  cat {archive}.part-* | tar -xzf -\n'
    f'cd {archive.removesuffix(".tar.gz")}\n./UeSim.sh\n```\n\n'
    '分卷不是独立压缩包，必须按文件名顺序合并。\n'
    'Parts are not independent archives; concatenate them in filename order.\n'
    'SHA256SUMS-full checks the reconstructed archive, not individual parts.\n')
print(json.dumps(manifest, indent=2))
PY
# Publish the completed local directory atomically; never overwrite existing assets.
mv -T --no-clobber -- "$work" "$output"
[[ ! -d $work ]] || { printf 'Destination appeared while building; refusing overwrite.\n' >&2; exit 1; }
trap - EXIT
printf 'Ready: %s/github (upload these files as Release assets)\n' "$output"
printf 'Full archive: %s/full/%s\n' "$output" "$archive"
