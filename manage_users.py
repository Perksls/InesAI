#!/usr/bin/env python3
"""
InesBot - Gestão de Utilizadores
Uso: python manage_users.py [comando] [args]

Comandos:
  create <username> <password> [--admin]   Criar utilizador
  list                                      Listar utilizadores
  delete <username>                         Apagar utilizador
  passwd <username> <nova_password>         Mudar password
  setup                                     Criar o primeiro utilizador interativamente
"""
import sys
import os
from pathlib import Path

# Garantir que backend está no path
sys.path.insert(0, str(Path(__file__).parent / "backend"))

# Apontar DB para o lugar certo
os.environ.setdefault("INESBOT_SECRET", "dev-only-change-in-production")

from auth import (
    init_auth_db, create_user, get_user_by_username,
    delete_user, change_password, list_users, DB_PATH
)


def cmd_create(args):
    if len(args) < 2:
        print("Uso: create <username> <password> [--admin]")
        return
    username, password = args[0], args[1]
    is_admin = "--admin" in args
    if get_user_by_username(username):
        print(f"❌ Utilizador '{username}' já existe.")
        return
    if len(password) < 6:
        print("❌ Password deve ter pelo menos 6 caracteres.")
        return
    uid = create_user(username, password, is_admin)
    role = "admin" if is_admin else "utilizador"
    print(f"✅ {role.capitalize()} '{username}' criado (id={uid})")


def cmd_list(_args):
    users = list_users()
    if not users:
        print("Nenhum utilizador encontrado.")
        return
    print(f"\n{'ID':<5} {'Username':<20} {'Admin':<8} {'Criado em'}")
    print("-" * 55)
    for u in users:
        admin = "✓" if u["is_admin"] else ""
        print(f"{u['id']:<5} {u['username']:<20} {admin:<8} {u['created_at']}")
    print()


def cmd_delete(args):
    if not args:
        print("Uso: delete <username>")
        return
    username = args[0]
    user = get_user_by_username(username)
    if not user:
        print(f"❌ Utilizador '{username}' não encontrado.")
        return
    confirm = input(f"Apagar '{username}' e todos os seus chats? (s/N): ").strip().lower()
    if confirm != "s":
        print("Cancelado.")
        return
    delete_user(user["id"])
    print(f"✅ Utilizador '{username}' apagado.")


def cmd_passwd(args):
    if len(args) < 2:
        print("Uso: passwd <username> <nova_password>")
        return
    username, new_password = args[0], args[1]
    user = get_user_by_username(username)
    if not user:
        print(f"❌ Utilizador '{username}' não encontrado.")
        return
    if len(new_password) < 6:
        print("❌ Password deve ter pelo menos 6 caracteres.")
        return
    change_password(user["id"], new_password)
    print(f"✅ Password de '{username}' alterada.")


def cmd_setup(_args):
    print("\n=== InesBot — Criar primeiro utilizador ===\n")
    users = list_users()
    if users:
        print("Já existem utilizadores:")
        cmd_list([])
        add_more = input("Queres criar mais um? (s/N): ").strip().lower()
        if add_more != "s":
            return

    username = input("Username: ").strip()
    if not username:
        print("❌ Username não pode ser vazio.")
        return
    if get_user_by_username(username):
        print(f"❌ '{username}' já existe.")
        return

    import getpass
    password = getpass.getpass("Password: ")
    confirm  = getpass.getpass("Confirmar password: ")
    if password != confirm:
        print("❌ Passwords não coincidem.")
        return
    if len(password) < 6:
        print("❌ Password deve ter pelo menos 6 caracteres.")
        return

    is_admin = input("Tornar admin? (s/N): ").strip().lower() == "s"
    uid = create_user(username, password, is_admin)
    print(f"\n✅ Utilizador '{username}' criado com sucesso (id={uid})")
    print("Podes agora iniciar o servidor e fazer login.\n")


COMMANDS = {
    "create": cmd_create,
    "list":   cmd_list,
    "delete": cmd_delete,
    "passwd": cmd_passwd,
    "setup":  cmd_setup,
}


if __name__ == "__main__":
    print(f"[DB: {DB_PATH}]")
    init_auth_db()

    args = sys.argv[1:]
    if not args or args[0] not in COMMANDS:
        print(__doc__)
        sys.exit(0)

    cmd = args[0]
    COMMANDS[cmd](args[1:])
