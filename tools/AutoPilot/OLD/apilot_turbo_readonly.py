#!/usr/bin/env python3
from __future__ import annotations
import enum
import subprocess
import sys
from dataclasses import dataclass
from typing import Final

ResultTriple: Final = tuple[int, str, str]

class ExecLayer(enum.Enum):
    ADB = "adb shell"

@dataclass(frozen=True)
class SecFERRO_ShellExecutor:
    layer: ExecLayer = ExecLayer.ADB

    def run(self, cmd: str) -> ResultTriple:
        full = f"{self.layer.value} {cmd}"
        try:
            r = subprocess.run(full, shell=True, capture_output=True, text=True, timeout=20)
            return r.returncode, r.stdout.strip(), r.stderr.strip()
        except subprocess.TimeoutExpired:
            return 124, "", f"timeout: {cmd[:60]}"
        except OSError as exc:
            return 1, "", str(exc)

    def getprop(self, key: str) -> str:
        rc, out, _ = self.run(f"getprop {key}")
        return out if rc == 0 else "[ERROR]"

    def getprop_all(self) -> dict[str, str]:
        rc, out, _ = self.run("getprop")
        props = {}
        if rc == 0:
            for line in out.split('\n'):
                if line.strip():
                    try:
                        k, v = line.split(']: [', 1)
                        k = k.lstrip('[')
                        v = v.rstrip(']')
                        props[k] = v
                    except ValueError:
                        pass
        return props

@dataclass(frozen=True)
class SecFERRO_PerformanceProfiler:
    shell: SecFERRO_ShellExecutor

    def diagnose_device(self) -> None:
        print("\n==[ SecFERRO PerformanceTuner v9.5.0-rc.2 — READ-ONLY DIAGNOSTICS ]===\n")
        
        props = self.shell.getprop_all()
        
        print("==[ DEVICE IDENTITY ]" + "=" * 50)
        for k in ['ro.product.model', 'ro.product.manufacturer', 'ro.build.version.release', 'ro.build.version.sdk']:
            print(f"  {k:<40} {props.get(k, '[N/A]')}")
        
        print("\n==[ SECURITY POSTURE ]" + "=" * 50)
        print(f"  ro.secure                          {props.get('ro.secure', '[N/A]')} (1=locked, 0=unlocked)")
        print(f"  ro.debuggable                      {props.get('ro.debuggable', '[N/A]')} (1=dev, 0=user)")
        
        print("\n==[ HWUI GRAPHICS PIPELINE ]" + "=" * 50)
        for k in ['debug.hwui.renderer', 'debug.renderengine.backend', 'debug.hwui.use_gpu_pixel_buffers']:
            v = props.get(k, '[not set]')
            print(f"  {k:<40} {v}")
        
        print("\n==[ STAGEFRIGHT MEDIA CODEC ]" + "=" * 50)
        for k in ['media.stagefright.enable-player', 'media.vcodec.preferhw', 'media.acodec.preferhw']:
            v = props.get(k, '[not set]')
            print(f"  {k:<40} {v}")
        
        print("\n==[ NETWORK + DNS ]" + "=" * 50)
        print(f"  net.dns1                           {props.get('net.dns1', '[system]')}")
        print(f"  net.dns2                           {props.get('net.dns2', '[system]')}")
        print(f"  net.tcp.default_init_rwnd          {props.get('net.tcp.default_init_rwnd', '[default]')}")
        
        print("\n==[ DALVIK VM TUNING ]" + "=" * 50)
        for k in ['dalvik.vm.heapsize', 'dalvik.vm.heapminfree', 'dalvik.vm.heapmaxfree']:
            v = props.get(k, '[default]')
            print(f"  {k:<40} {v}")
        
        print("\n==[ SECURITY STATUS ]" + "=" * 50)
        secure = props.get('ro.secure')
        debuggable = props.get('ro.debuggable')
        
        if secure == '1' and debuggable == '0':
            print("  [✗] Device is PRODUCTION-LOCKED")
            print("      setprop() requires root/su — NOT available")
            print("      Shizuku/rish detected but uid=2000 (no privilege elevation)")
            print("\n  → OPTIMIZATION MODE: DRY-RUN SIMULATION ONLY")
        else:
            print("  [✓] Device may allow modifications")
        
        print("\n==[ DIAGNOSTIC COMPLETE ]===\n")

def main():
    shell = SecFERRO_ShellExecutor()
    profiler = SecFERRO_PerformanceProfiler(shell)
    profiler.diagnose_device()

if __name__ == "__main__":
    main()
