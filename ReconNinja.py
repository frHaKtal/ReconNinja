import sys
import os
import concurrent.futures
import sqlite3
from prompt_toolkit import PromptSession, print_formatted_text
from prompt_toolkit.completion import Completer, Completion
from prompt_toolkit.shortcuts import print_formatted_text
#from enum_task import add_dom, setup_database
from enum_task import add_dom
from setup_database import setup_database
import subprocess
import base64
from tqdm import tqdm
import multiprocessing

# Connexion à la base de données
#conn = sqlite3.connect('database.db')
#cursor = conn.cursor()

# Dictionnaire contenant les commandes et leurs descriptions
commands_with_descriptions = {
    'exit': 'Exit the program',
    'add': 'Add domain1.com domain2.com or *.domain.com',
    'add_com': 'Add comment to domain or program (add_com domain/program domain.com "xx")',
    'rm': 'Remove a domain (without http) or program (rm domain/program xx)',
    'list': 'Domain of program list (list domain/program/ip)',
    'clear': 'Clear screen',
    'scan': 'Perform a signature scan on all discovered servers',
}

class CommandCompleter(Completer):
    def get_completions(self, document, complete_event):
        # Renvoyer les suggestions et descriptions des commandes
        word_before_cursor = document.get_word_before_cursor()
        for command, description in commands_with_descriptions.items():
            if command.startswith(word_before_cursor):
                yield Completion(command, start_position=-len(word_before_cursor), display_meta=description)


def add_domains_in_parallel_multiprocessing(program_name, domains):
    # Créer une barre de progression avec le nombre total de domaines
    with tqdm(total=len(domains), desc="Processing domains", unit="domain") as pbar:
        # Utiliser multiprocessing pour exécuter add_dom en parallèle
        with multiprocessing.Pool(processes=multiprocessing.cpu_count()) as pool:
            results = []
            for domain in domains:
                result = pool.apply_async(add_dom, (program_name, domain))
                results.append(result)
            # Attendre que toutes les tâches soient terminées
            for result in results:
                try:
                    result.get()  # Bloque jusqu'à la fin de chaque tâche
                except Exception as e:
                    print(f"Error during domain addition: {e}")
                finally:
                    # Incrémenter la barre de progression après chaque domaine traité
                    pbar.update(1)

def add_domains_in_parallel_multithread(program_name, domains):
    # Créer une barre de progression avec le nombre total de domaines
    with tqdm(total=len(domains), desc="Processing domains", unit="domain") as pbar:
        with concurrent.futures.ThreadPoolExecutor() as executor:
            futures = [executor.submit(add_dom, program_name, domain) for domain in domains]
            for future in concurrent.futures.as_completed(futures):
                try:
                    future.result()  # Bloque jusqu'à la fin de chaque tâche
                except Exception as e:
                    print(f"Error during domain addition: {e}")
                finally:
                    # Incrémenter la barre de progression après chaque domaine traité
                    pbar.update(1)

def enum_domain(domain_name):
    print(f"✔️  Enumeration for domain: \033[1m{domain_name}\033[0m")
    result = subprocess.run(f"subfinder -d {domain_name} -silent",
                            shell=True,
                            stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE,
                            text=True)
    return result.stdout

def display_screenshot_with_imgcat(screenshot_data):
    # Convertir les données blob en image utilisable
    #print(screenshot_data)
    image_data = base64.b64decode(screenshot_data)

    # Sauvegarder temporairement l'image pour imgcat
    temp_image_path = "/tmp/temp_screenshot.png"
    with open(temp_image_path, "wb") as img_file:
        img_file.write(image_data)

    # Utiliser imgcat pour afficher l'image dans le terminal
    os.system(f"imgcat {temp_image_path}")

    # Supprimer le fichier temporaire après affichage
    os.remove(temp_image_path)


def rm(entity_name, entity_type):
    #cursor = conn.cursor()
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()
    if entity_type == 'program':
        # Vérifier si le programme existe
        cursor.execute('SELECT id FROM programs WHERE program_name = ?', (entity_name,))
        program = cursor.fetchone()
        if program:
            # Supprimer le programme
            cursor.execute('DELETE FROM programs WHERE id = ?', (program[0],))
            conn.commit()
            print(f"✔️ Program \033[1m'{entity_name}'\033[0m has been deleted.")
        else:
            print(f"❌ Program \033[1m'{entity_name}'\033[0m not found.")

    elif entity_type == 'domain':
        # Vérifier si le domaine existe
        cursor.execute('SELECT id FROM domains WHERE domain_name = ?', (entity_name,))
        domain = cursor.fetchone()

        if domain:
            # Supprimer le domaine
            cursor.execute('DELETE FROM domains WHERE id = ?', (domain[0],))
            conn.commit()
            print(f"✔️ Domain \033[1m'{entity_name}'\033[0m has been deleted.")
        else:
            print(f"❌ Domain \033[1m'{entity_name}'\033[0m not found.")

    else:
        print("❌ Invalid entity type. Use 'program' or 'domain'.")

    conn.close()
    cursor.close()

def add_com(target_type, target_name, comment):
    """
    Ajoute ou met à jour un commentaire pour un programme ou un domaine.
    :param target_type: Le type de cible ('program' ou 'domain')
    :param target_name: Le nom du programme ou du domaine
    :param comment: Le commentaire à ajouter ou mettre à jour
    """
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()

    if target_type == 'program':
        # Vérifier si le programme existe
        cursor.execute('SELECT id FROM programs WHERE program_name = ?', (target_name,))
        program = cursor.fetchone()

        if program:
            program_id = program[0]
            # Ajouter ou mettre à jour le commentaire du programme
            cursor.execute('UPDATE programs SET com = ? WHERE id = ?', (comment, program_id))
            conn.commit()
            print(f"✔️ Comment added to program '{target_name}'")
        else:
            print(f"❌ Program '{target_name}' not found.")
    elif target_type == 'domain':
        # Vérifier si le domaine existe
        cursor.execute('SELECT id FROM domains WHERE domain_name = ?', (target_name,))
        domain = cursor.fetchone()

        if domain:
            domain_id = domain[0]
            # Ajouter ou mettre à jour le commentaire du domaine
            cursor.execute('UPDATE domain_details SET com = ? WHERE domain_id = ?', (comment, domain_id))
            conn.commit()
            print(f"✔️ Comment added to domain '{target_name}'")
        else:
            print(f"❌ Domain '{target_name}' not found.")
    else:
        print(f"❌ Invalid target type. Use 'program' or 'domain'.")

    conn.close()
    cursor.close()

def list(entity_type, program_name=None):
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()

    if entity_type == 'program':
        cursor.execute('''
            SELECT id, program_name, com FROM programs
        ''')
        programs = cursor.fetchall()

        if programs:
            print("📄 List of programs:")
            for program in programs:
                print(f"Program: \033[1m{program[1]}\033[0m - Comment: \033[1m{program[2]}\033[0m")
        else:
            print("❌ No programs found.")

    elif entity_type == 'domain':
        if program_name:
            # Récupérer l'ID du programme
            cursor.execute('SELECT id FROM programs WHERE program_name = ?', (program_name,))
            program = cursor.fetchone()

            if program:
                program_id = program[0]

                # Récupérer le nombre de domaines pour ce programme
                cursor.execute('''
                    SELECT COUNT(*) FROM domains
                    WHERE program_id = ?
                ''', (program_id,))
                domain_count = cursor.fetchone()[0]

                print(f"📝 Number of domains for program \033[1m{program_name}\033[0m: \033[1m{domain_count}\033[0m")

                # Afficher les domaines du programme
                cursor.execute('''
                    SELECT domains.domain_name, domain_details.http_status, domain_details.ip, domain_details.title,
                           domain_details.techno, domain_details.open_port, domain_details.screen, domain_details.spfdmarc, domain_details.com
                    FROM domains
                    INNER JOIN domain_details ON domains.id = domain_details.domain_id
                    WHERE domains.program_id = ?
                    ORDER BY domain_details.screen IS NOT NULL DESC,
                             CASE
                                WHEN domain_details.http_status = 200 THEN 1
                                WHEN domain_details.http_status IS NULL THEN 3
                                ELSE 2
                             END
                ''', (program_id,))
                domains = cursor.fetchall()

                if domains:
                    print(f"📄 List of domains for program \033[1m{program_name}\033[0m:")
                    for domain in domains:
                        domain_name, http_status, ip, title, techno, open_port, screen, spfdmarc, comment = domain
                        print(f"\033[48;5;240m🌐 http://\033[1m{domain_name}\033[0m\n"
                              f"\033[48;5;240mHttp status: \033[1m{http_status}\033[0m\n"
                              f"\033[48;5;240mIP: \033[1m{ip}\033[0m\n"
                              f"\033[48;5;240mTitle: \033[1m{title}\033[0m\n"
                              f"\033[48;5;240mTech: \033[1m{techno}\033[0m\n"
                              f"\033[48;5;240mOpen port: \033[1m{open_port}\033[0m\n"
                              f"\033[48;5;240mSpf/Dmarc: \033[1m{spfdmarc}\033[0m\n")

                        if comment:
                            print(f"\033[48;5;240mComment: \033[1m{comment}\033[0m\n")

                        if screen:
                            display_screenshot_with_imgcat(screen)
                            print("\n")
                        else:
                            print("No screenshot available.")
                            print("\n")
                else:
                    print(f"❌ No domains found for program \033[1m{program_name}\033[0m.")
            else:
                print(f"❌ Program \033[1m{program_name}\033[0m not found.")

        else:
            # Récupérer le nombre total de domaines
            cursor.execute('SELECT COUNT(*) FROM domains')
            total_domains = cursor.fetchone()[0]
            print(f"📝 Total number of domains: \033[1m{total_domains}\033[0m")

            # Afficher tous les domaines
            cursor.execute('''
                SELECT domains.domain_name, domain_details.http_status, domain_details.spfdmarc, domain_details.ip, domain_details.title,
                       domain_details.techno, domain_details.open_port, domain_details.screen, domain_details.spfdmarc, domain_details.com
                FROM domains
                INNER JOIN domain_details ON domains.id = domain_details.domain_id
                ORDER BY domain_details.screen IS NOT NULL DESC, domain_details.http_status DESC
            ''')
            domains = cursor.fetchall()

            if domains:
                print("📄 List of domains:")
                for domain in domains:
                    domain_name, http_status, ip, title, techno, open_port, screen, spfdmarc, comment = domain
                    print(f"\033[48;5;240m🌐 http://\033[1m{domain_name}\033[0m\n"
                          f"\033[48;5;240mHttp status: \033[1m{http_status}\033[0m\n"
                          f"\033[48;5;240mIP: \033[1m{ip}\033[0m\n"
                          f"\033[48;5;240mTitle: \033[1m{title}\033[0m\n"
                          f"\033[48;5;240mTech: \033[1m{techno}\033[0m\n"
                          f"\033[48;5;240mOpen port: \033[1m{open_port}\033[0m\n"
                          f"\033[48;5;240mSpf/Dmarc: \033[1m{spfdmarc}\033[0m\n")

                    if comment:
                        print(f"\033[48;5;240mComment: \033[1m{comment}\033[0m\n")

                    if screen:
                        display_screenshot_with_imgcat(screen)
                        print("\n")
                    else:
                        print("No screenshot available.")
                        print("\n")
            else:
                print("❌ No domains found.")

    elif entity_type == 'ip':
        cursor.execute('''
            SELECT DISTINCT domain_details.ip FROM domain_details
            WHERE domain_details.ip IS NOT NULL
            ORDER BY domain_details.ip
        ''')
        ips = cursor.fetchall()

        if ips:
            print("📄 List of IP addresses:")
            for ip in ips:
                print(f"\033[1m{ip[0]}\033[0m")
        else:
            print("❌ No IPs found.")

    else:
        print("❌ Invalid entity type. Use 'program', 'domain', or 'ip'.")
    cursor.close()
    conn.close()

def add_program(program_name):
    # Ouvrir une connexion à la base de données
    #conn = get_db_connection()
    #cursor = conn.cursor()
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()

    try:
        # Vérifier si le programme existe déjà
        cursor.execute('SELECT id FROM programs WHERE program_name = ?', (program_name,))
        existing_program = cursor.fetchone()

        if existing_program:
            print(f"⚠️  Program '{program_name}' already exists.")
        else:
            # Ajouter le programme s'il n'existe pas
            cursor.execute('INSERT INTO programs (program_name) VALUES (?)', (program_name,))
            conn.commit()
            print(f"✔️  Program '{program_name}' added successfully.")
    except Exception as e:
        print(f"❌ Failed to add program '{program_name}': {e}")
    finally:
        cursor.close()
        conn.close()

def main():
    session = PromptSession()

    # Message d'instruction
    print_formatted_text("\n【Welcome to ReconNinja v1.0 by _frHaKtal_】")
    print_formatted_text("‼️ Press tab for autocompletion and available commands\n")

    # Créer la base de données et les tables si elles n'existent pas déjà
    setup_database()

    # Ajouter le programme depuis l'argument de ligne de commande
    program_name = sys.argv[1]
    command_completer = CommandCompleter()

    add_program(sys.argv[1])
    while True:
        try:
            user_input = session.prompt(f'{program_name} ▶︎ ', completer=command_completer)
            parts = user_input.split()
            if parts:
                command = parts[0]
                args = parts[1:]

                if command == 'add':
                    domains = []
                    for domain in args:
                        if '*.' in domain:
                            domain_enum = enum_domain(domain.lstrip('*.'))
                            domains.extend(domain_enum.splitlines())
                            print(f"✔️  \033[1m{len(domains)}\033[0m domain find")
                        else:
                            domains.append(domain)

                    # Lancer l'ajout des domaines en parallèle
                    #add_domains_in_parallel(program_name, domains)
                    add_domains_in_parallel_multiprocessing(program_name, domains)
                elif command == 'list':
                    if args:
                      list(args[0],sys.argv[1])
                elif command == 'clear':
                    os.system('clear')
                elif command == 'add_com':
                    if len(args) >= 3:
                        target_type = args[0]
                        target_name = args[1]
                        comment = " ".join(args[2:])  # Prendre le reste des arguments comme commentaire
                        add_com(target_type, target_name, comment)
                    else:
                        print("❌ Usage: add_com [program|domain] [name] [comment]")
                elif command == 'rm':
                    rm(args[1],args[0])
                elif command == 'exit':
                    print("Exiting...")
                    break

                # Autres commandes...

        except (KeyboardInterrupt, EOFError):
            print("Exiting...")
            break

    #conn.close()

if __name__ == "__main__":
    main()
