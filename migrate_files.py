import os
import sys
import time
import stat
import paramiko
from dotenv import load_dotenv
from paramiko import SSHClient, AutoAddPolicy, RSAKey, Ed25519Key

load_dotenv()

def get_days_from_env():
    try:
        return int(os.getenv("FILE_MODIFIED_DAYS", "15"))
    except ValueError:
        return 15

def parse_ssh_configs():
    """
    Agrupa todas las conexiones SSH y sus reglas de migración.
    Retorna un dict con estructura:
    {
        "SSH1": { "host":..., "port":..., "user":..., "password":..., "key_path":..., "passphrase":..., "rules":[...] },
        "SSH2": { ... }
    }
    """
    configs = {}
    for key, value in os.environ.items():
        if key.startswith("SSH") and "_HOST" in key:
            idx = key.split("_")[0]
            configs.setdefault(idx, {})["host"] = value
        elif key.startswith("SSH") and "_PORT" in key:
            idx = key.split("_")[0]
            configs.setdefault(idx, {})["port"] = int(value)
        elif key.startswith("SSH") and "_USER" in key:
            idx = key.split("_")[0]
            configs.setdefault(idx, {})["user"] = value
        elif key.startswith("SSH") and "_PASSWORD" in key:
            idx = key.split("_")[0]
            configs.setdefault(idx, {})["password"] = value.strip()
        elif key.startswith("SSH") and "_KEY_PATH" in key:
            idx = key.split("_")[0]
            configs.setdefault(idx, {})["key_path"] = os.path.normpath(value.strip())
        elif key.startswith("SSH") and "_KEY_PASSPHRASE" in key:
            idx = key.split("_")[0]
            configs.setdefault(idx, {})["passphrase"] = value
        elif key.startswith("SSH") and "_FILE_MIGRATION_RULE_" in key:
            idx = key.split("_")[0]
            remote, local = value.split("|")
            configs.setdefault(idx, {}).setdefault("rules", []).append({
                "remote": remote.strip(),
                "local": os.path.normpath(local.strip())
            })
    return configs

def connect_ssh(cfg):
    ssh = SSHClient()
    ssh.set_missing_host_key_policy(AutoAddPolicy())
    try:
        if cfg.get("password"):
            ssh.connect(
                hostname=cfg["host"],
                port=cfg.get("port", 22),
                username=cfg["user"],
                password=cfg["password"]
            )
            print(f"🔐 {cfg['host']} conectado por contraseña")
        elif cfg.get("key_path"):
            if not os.path.isfile(cfg["key_path"]):
                print(f"❌ Archivo de clave no encontrado: {cfg['key_path']}")
                return None
            if "ed25519" in cfg["key_path"].lower():
                pkey = Ed25519Key.from_private_key_file(cfg["key_path"], password=cfg.get("passphrase"))
            else:
                pkey = RSAKey.from_private_key_file(cfg["key_path"], password=cfg.get("passphrase"))
            ssh.connect(
                hostname=cfg["host"],
                port=cfg.get("port", 22),
                username=cfg["user"],
                pkey=pkey
            )
            print(f"🔐 {cfg['host']} conectado por clave privada")
        else:
            print("❌ No se definió método de autenticación")
            return None
        return ssh
    except Exception as e:
        print(f"❌ Error en conexión SSH {cfg['host']}: {e}")
        return None

def copy_recursive(sftp, remote_dir, local_dir, cutoff):
    """
    Copia archivos y subdirectorios recursivamente desde remote_dir a local_dir
    preservando fechas y filtrando por cutoff (últimos N días).
    """
    os.makedirs(local_dir, exist_ok=True)
    for entry in sftp.listdir_attr(remote_dir):
        remote_path = f"{remote_dir}/{entry.filename}"
        local_path = os.path.join(local_dir, entry.filename)

        if stat.S_ISDIR(entry.st_mode):
            copy_recursive(sftp, remote_path, local_path, cutoff)
        else:
            if entry.st_mtime >= cutoff:
                sftp.get(remote_path, local_path)
                attrs = sftp.stat(remote_path)
                os.utime(local_path, (attrs.st_atime, attrs.st_mtime))
                print(f"   → {remote_path} copiado a {local_path} [fechas preservadas]")

def validate_rules(sftp, rules):
    valid_rules, invalid_rules = [], []
    for rule in rules:
        remote_dir = rule["remote"]
        local_dir = rule["local"]
        try:
            sftp.listdir(remote_dir)
        except IOError:
            invalid_rules.append({**rule, "error": f"Directorio remoto no existe: {remote_dir}"})
            continue
        try:
            os.makedirs(local_dir, exist_ok=True)
        except Exception as e:
            invalid_rules.append({**rule, "error": f"No se pudo crear directorio local {local_dir}: {e}"})
            continue
        valid_rules.append(rule)
    return valid_rules, invalid_rules

def migrate_recent_files(sftp, rules):
    days = get_days_from_env()
    cutoff = time.time() - (days * 86400)

    for rule in rules:
        remote_dir = rule["remote"]
        local_dir = rule["local"]
        print(f"\n📂 Migrando recursivamente {remote_dir} → {local_dir} (últimos {days} días)")
        try:
            copy_recursive(sftp, remote_dir, local_dir, cutoff)
        except Exception as e:
            print(f"❌ Error en {remote_dir}: {e}")

def main():
    ssh_configs = parse_ssh_configs()
    if not ssh_configs:
        print("❌ No se encontraron configuraciones SSH en .env")
        sys.exit(1)

    for name, cfg in ssh_configs.items():
        print(f"\n🔗 Procesando {name}: {cfg['host']}:{cfg.get('port',22)} ({cfg['user']})")
        ssh = connect_ssh(cfg)
        if not ssh:
            continue
        sftp = ssh.open_sftp()
        valid_rules, invalid_rules = validate_rules(sftp, cfg.get("rules", []))
        if invalid_rules:
            print("\n❌ Reglas inválidas encontradas:")
            for r in invalid_rules:
                print(f" - {r['remote']} → {r['local']}: {r['error']}")
        if valid_rules:
            migrate_recent_files(sftp, valid_rules)
        sftp.close()
        ssh.close()
        print(f"\n✅ Migración finalizada para {name}")

if __name__ == "__main__":
    main()