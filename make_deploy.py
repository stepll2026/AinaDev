# -*- coding: utf-8 -*-
"""本地打包部署包（排除大依赖目录）。"""
import os
import tarfile

ROOT = r"F:\NAS\WorkBuddy\AinaDev\ai-native-community"
OUT = os.path.join(ROOT, "deploy.tar.gz")

EXCLUDE_DIRS = {"node_modules", ".venv", ".next", "uploads", ".git", "__pycache__", ".turbo", "vditor"}
EXCLUDE_SUFFIX = {".pyc", ".log"}


def should_skip(path: str) -> bool:
    parts = path.replace("\\", "/").split("/")
    for p in parts:
        if p in EXCLUDE_DIRS:
            return True
    if path.endswith(".pyc") or path.endswith(".log"):
        return True
    # 敏感文件一律不入部署包（.env / 凭据脚本 / 本地联调脚本）
    name = parts[-1]
    if name == ".env" or name.startswith("_") or name in {
        "deploy_to_server.py", "update_server.py", "sync_server_main.py",
        "check_prod_env.py", "check_env2.py", "check_prod_health.py",
        "verify_prod.py", "verify_mcp.py", "verify_server.py", "verify_github_sync.py",
        "make_deploy.py", "check_deploy.py", "check_deploy2.py", "check_deploy3.py", "check_deploy4.py",
    }:
        return True
    return False


def main():
    if os.path.exists(OUT):
        os.remove(OUT)
    count = 0
    with tarfile.open(OUT, "w:gz") as tf:
        for name in ["apps", "docker", "docker-compose.yml", "docker-compose.prod.yml", ".env.example", "README.md", "start-dev.ps1", ".gitignore"]:
            src = os.path.join(ROOT, name)
            if not os.path.exists(src):
                continue
            if os.path.isdir(src):
                for root, dirs, files in os.walk(src):
                    dirs[:] = [d for d in dirs if d not in EXCLUDE_DIRS]
                    for f in files:
                        fp = os.path.join(root, f)
                        if should_skip(fp):
                            continue
                        arc = os.path.relpath(fp, ROOT).replace("\\", "/")
                        tf.add(fp, arcname=arc)
                        count += 1
            else:
                arc = os.path.relpath(src, ROOT).replace("\\", "/")
                tf.add(src, arcname=arc)
                count += 1
    size = os.path.getsize(OUT) / 1024 / 1024
    print(f"打包完成: {count} 个文件, {size:.1f} MB -> {OUT}")


if __name__ == "__main__":
    main()
