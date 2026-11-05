# MiuiCamera.apk is stored as <100 MB parts (GitHub file size limit);
# reassemble it when build/envsetup.sh is sourced.
_mcv_apk_dir="$(dirname "${BASH_SOURCE[0]}")/xiaomi/proprietary/system/priv-app/MiuiCamera"
if [ -f "$_mcv_apk_dir/MiuiCamera.apk.part00" ] &&
        ! (cd "$_mcv_apk_dir" && sha256sum --status -c MiuiCamera.apk.sha256 2>/dev/null); then
    cat "$_mcv_apk_dir"/MiuiCamera.apk.part[0-9][0-9] > "$_mcv_apk_dir/MiuiCamera.apk"
    if ! (cd "$_mcv_apk_dir" && sha256sum --status -c MiuiCamera.apk.sha256); then
        echo "miuicamera-violet: reassembled MiuiCamera.apk does not match MiuiCamera.apk.sha256" >&2
    fi
fi
unset _mcv_apk_dir
