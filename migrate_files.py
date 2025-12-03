import os
import sys
import time
import paramiko
import stat
from dotenv import load_dotenv
from paramiko import SSHClient, AutoAddPolicy, RSAKey, Ed25519Key

load_dotenv()

def get_file_rules():
    rules = []
    for key, value in os.environ.items():
        if key.startswith("FILE_MIGRATION_RULE_"):
            parts = value.strip().split("|")
            if len(parts) == 2:
                rules.append({
                    "remote": parts[0],
                    "local": parts[1]
                })
            else:
                print(f"⚠️ Regla mal formada: {value}")
    return rules

def get_days_from_env():
    try:
        return int(os.getenv("FILE_MODIFIED_DAYS", "15"))
    except ValueError:
        return 15

def connect_ssh():
    host = os.getenv("SSH_HOST")
    port = int(os.getenv("SSH_PORT", "22"))
    user = os.getenv("SSH_USER")

    password = os.getenv("SSH_PASSWORD", "").strip()
    key_path = os.getenv("SSH_KEY_PATH", "").strip()
    passphrase = os.getenv("SSH_KEY_PASSPHRASE", None)

    ssh = SSHClient()
    ssh.set_missing_host_key_policy(AutoAddPolicy())

    try:
        if password:
            ssh.connect(hostname=host, port=port, username=user, password=password)
            print("🔐 Conectado por contraseña")
        elif key_path:
            key_path = os.path.normpath(key_path)
            if not os.path.isfile(key_path):
                print(f"❌ Archivo de clave no encontrado: {key_path}")
                sys.exit(1)

            if "ed25519" in key_path.lower():
                pkey = Ed25519Key.from_private_key_file(key_path, password=passphrase)
            else:
                pkey = RSAKey.from_private_key_file(key_path, password=passphrase)

            ssh.connect(hostname=host, port=port, username=user, pkey=pkey)
            print("🔐 Conectado por clave privada")
        else:
            print("❌ No se definió SSH_PASSWORD ni SSH_KEY_PATH")
            sys.exit(1)

        return ssh

    except Exception as e:
        print(f"❌ Error en conexión SSH: {e}")
        sys.exit(1)

def validate_rules(sftp, rules):
    valid_rules = []
    invalid_rules = []

    for rule in rules:
        remote_dir = rule["remote"]
        local_dir = os.path.normpath(rule["local"])

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

    total_files_global = 0
    copied_files_global = 0

    # Calcular total global
    for rule in rules:
        try:
            files = sftp.listdir_attr(rule["remote"])
            total_files_global += len([f for f in files if f.st_mtime >= cutoff])
        except Exception:
            pass

    for rule in rules:
        remote_dir = rule["remote"]
        local_dir = os.path.normpath(rule["local"])

        try:
            files = sftp.listdir_attr(remote_dir)
            recent_files = [f for f in files if f.st_mtime >= cutoff]

            total_files = len(recent_files)
            copied_files = 0

            print(f"\n📂 Migrando archivos modificados en los últimos {days} días")
            print(f"   {remote_dir} → {local_dir} ({total_files} archivos)")

            for f in recent_files:
                remote_path = f"{remote_dir}/{f.filename}"
                local_path = os.path.join(local_dir, f.filename)

                sftp.get(remote_path, local_path)
                copied_files += 1
                copied_files_global += 1

                percent_dir = (copied_files / total_files) * 100 if total_files else 100
                percent_global = (copied_files_global / total_files_global) * 100 if total_files_global else 100

                print(f"   → {f.filename} ({copied_files}/{total_files}, {percent_dir:.1f}%)")
                print(f"🌍 Progreso global: {copied_files_global}/{total_files_global} ({percent_global:.1f}%)")

            if total_files == 0:
                print("   ⚠️ No hay archivos recientes en este directorio.")

        except Exception as e:
            print(f"❌ Error en {remote_dir}: {e}")
            sys.exit(1)

if __name__ == "__main__":
    rules = get_file_rules()
    ssh = connect_ssh()
    sftp = ssh.open_sftp()

    valid_rules, invalid_rules = validate_rules(sftp, rules)
    if invalid_rules:
        print("\n❌ Se encontraron reglas inválidas, abortando migración:")
        for r in invalid_rules:
            print(f" - {r['remote']} → {r['local']}: {r['error']}")
        sftp.close()
        ssh.close()
        sys.exit(1)

    migrate_recent_files(sftp, valid_rules)

    sftp.close()
    ssh.close()
    print("\n✅ Migración de archivos finalizada")