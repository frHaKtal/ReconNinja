import sys
import os
import concurrent.futures
import sqlite3
from prompt_toolkit import PromptSession, print_formatted_text
from prompt_toolkit.completion import Completer, Completion
from prompt_toolkit.shortcuts import print_formatted_text
from enum_task import add_dom
from setup_database import setup_database
import subprocess
import base64
from tqdm import tqdm
import multiprocessing
import argparse
from rich.console import Console
from rich.table import Table
from rich.panel import Panel

def lolcat(text):
    os.system(f"echo '{text}' | lolcat")

# Dictionnaire contenant les commandes et leurs descriptions
commands_with_descriptions = {
    'exit': 'Exit the program',
    'add': 'Add domain1.com domain2.com or *.domain.com',
    'add_com': 'Add comment to domain or program (add_com domain/program domain.com "xx")',
    'rm': 'Remove a domain (without http) or program (rm domain/program xx)',
    'list': 'Domain of program list (list domain/ip/program)',
    'show': 'Show domain list with screenshot',
    'search': 'Search in domain list (search xx)',
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
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()

    try:
        if entity_type == 'program':
            # Vérifier si le programme existe
            cursor.execute('SELECT id FROM programs WHERE program_name = ?', (entity_name,))
            program = cursor.fetchone()
            if program:
                program_id = program[0]
                # Supprimer les domaines associés au programme
                cursor.execute('DELETE FROM domains WHERE program_id = ?', (program_id,))
                # Supprimer le programme
                cursor.execute('DELETE FROM programs WHERE id = ?', (program_id,))
                conn.commit()
                print(f"✔️ Program \033[1m'{entity_name}'\033[0m and its associated domains have been deleted.")
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
    finally:
        # Fermer le curseur avant de fermer la connexion
        cursor.close()
        conn.close()




def add_com(target_type, target_name, comment):
    """
    Ajoute ou met à jour un commentaire pour un programme ou un domaine.
    :param target_type: Le type de cible ('program' ou 'domain')
    :param target_name: Le nom du programme ou du domaine
    :param comment: Le commentaire à ajouter ou mettre à jour
    """
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()

    try:
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

    finally:
        # Fermer le curseur avant la connexion
        cursor.close()
        conn.close()

def show(program_name=None):

    console = Console()
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()

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

            # Récupérer les domaines du programme avec le phash
            cursor.execute('''
                SELECT domains.domain_name, domain_details.http_status, domain_details.ip, domain_details.title,
                       domain_details.techno, domain_details.open_port, domain_details.screen, domain_details.phash, domain_details.spfdmarc,
                       domain_details.method, domain_details.com, domain_details.phash
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
                print(f"\n📄 List of domains for program \033[1m{program_name}\033[0m:")

                # Dictionnaire pour grouper les domaines par phash
                grouped_domains = {}

                for domain in domains:
                    domain_name, http_status, ip, title, techno, open_port, screen, phash, spfdmarc, method, comment, phash = domain
                    if phash not in grouped_domains:
                        grouped_domains[phash] = []
                    grouped_domains[phash].append(domain)

                # Afficher les groupes de domaines par phash
                for phash, group in grouped_domains.items():
                    if len(group) > 1:
                        print(f"⚠️  Domains with identical phash \033[1m{phash}\033[0m:")

                    for domain in group:
                        domain_name, http_status, ip, title, techno, open_port, screen, phash, spfdmarc, method, comment, phash = domain
                        console.rule("[bold blue]Domains Overview[/bold blue]")
                        console.print(f"[dim]🌐 Domain:[/dim] [bold][link=https://{domain_name}]{domain_name}[/link][/bold]")
                        console.print(f"[dim]Http status:[/dim] [bold]{http_status}[/bold]")
                        console.print(f"[dim]Http method:[/dim] [bold]{method}[/bold]")
                        console.print(f"[dim]IP:[/dim] [bold]{ip}[/bold]")
                        console.print(f"[dim]Title:[/dim] [bold]{title}[/bold]")
                        console.print(f"[dim]Tech:[/dim] [bold]{techno}[/bold]")
                        console.print(f"[dim]Open port:[/dim] [bold]{open_port}[/bold]")
                        console.print(f"[dim]Spf/Dmarc:[/dim] [bold]{spfdmarc}[/bold]")

                        if comment:
                            console.print(f"[dim]Comment:[/dim] [bold]{comment}[/bold]")
                        if screen:
                            #screenshot_panel = Panel("Screenshot available", title="Screenshot", border_style="green")
                            #console.print(screenshot_panel)
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
        print("❌ No program name provided.")

    cursor.close()
    conn.close()


def search(search_text, program_name):
    console = Console()
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()

    # Récupérer l'ID du programme en fonction de son nom
    cursor.execute('SELECT id FROM programs WHERE program_name = ?', (program_name,))
    program = cursor.fetchone()

    if not program:
        console.print(f"[bold red]❌ Program '{program_name}' not found.[/bold red]")
        cursor.close()
        conn.close()
        return

    program_id = program[0]

    # Rechercher dans plusieurs colonnes pour le programme en cours
    query = '''
        SELECT domains.domain_name, domain_details.http_status, domain_details.ip, domain_details.title,
               domain_details.techno, domain_details.open_port, domain_details.screen, domain_details.spfdmarc,
               domain_details.method, domain_details.com
        FROM domains
        INNER JOIN domain_details ON domains.id = domain_details.domain_id
        WHERE domains.program_id = ?
        AND (
            domains.domain_name LIKE ?
            OR domain_details.http_status LIKE ?
            OR domain_details.ip LIKE ?
            OR domain_details.title LIKE ?
            OR domain_details.techno LIKE ?
            OR domain_details.open_port LIKE ?
            OR domain_details.spfdmarc LIKE ?
            OR domain_details.method LIKE ?
        )
        ORDER BY domain_details.screen IS NOT NULL DESC,  -- D'abord ceux avec un screenshot
                 domain_details.ip IS NOT NULL DESC      -- Puis ceux avec une IP
    '''

    search_wildcard = f'%{search_text}%'
    cursor.execute(query, (
        program_id, search_wildcard, search_wildcard, search_wildcard, search_wildcard,
        search_wildcard, search_wildcard, search_wildcard, search_wildcard
    ))

    domains = cursor.fetchall()

    if domains:
        console.print(f"[bold green]📄 List of domains matching '{search_text}' in program '{program_name}':[/bold green]")
        for domain in domains:
            domain_name, http_status, ip, title, techno, open_port, screen, spfdmarc, method, com = domain
            console.rule("[bold blue]Domains Overview[/bold blue]")
            console.print(f"[dim]🌐 Domain:[/dim] [bold][link=https://{domain_name}]{domain_name}[/link][/bold]")
            console.print(f"[dim]Http status:[/dim] [bold]{http_status}[/bold]")
            console.print(f"[dim]Http method:[/dim] [bold]{method}[/bold]")
            console.print(f"[dim]IP:[/dim] [bold]{ip}[/bold]")
            console.print(f"[dim]Title:[/dim] [bold]{title}[/bold]")
            console.print(f"[dim]Tech:[/dim] [bold]{techno}[/bold]")
            console.print(f"[dim]Open port:[/dim] [bold]{open_port}[/bold]")
            console.print(f"[dim]Spf/Dmarc:[/dim] [bold]{spfdmarc}[/bold]")

            if com:
                console.print(f"[dim]Comment:[/dim] [bold]{com}[/bold]")

            if screen:
                display_screenshot_with_imgcat(screen)
                console.print("\n")
            else:
                console.print("[bold red]No screenshot available.[/bold red]")
                console.print("\n")
    else:
        console.print(f"[bold red]❌ No domains found containing '{search_text}' in any field in program '{program_name}'.[/bold red]")

    cursor.close()
    conn.close()


def list(entity_type, program_name=None):
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()

    if entity_type == 'program':
        cursor.execute('''
            SELECT id, program_name, com FROM programs
        ''')
        programs = cursor.fetchall()

        if programs:
            print("\n📄 List of programs:")
            for program in programs:
                print(f"Program: \033[1m{program[1]}\033[0m - Comment: \033[1m{program[2]}\033[0m")
        else:
            print("❌ No programs found.")

    elif entity_type == 'domain':
        if program_name:
            # Récupérer l'ID du programme en fonction de son nom
            cursor.execute('''
                SELECT id FROM programs WHERE program_name = ?
            ''', (program_name,))
            program = cursor.fetchone()

            if program:
                program_id = program[0]
                # Récupérer les domaines associés au programme
                cursor.execute('''
                    SELECT domain_name FROM domains
                    WHERE program_id = ?
                    ORDER BY domain_name
                ''', (program_id,))
                domains = cursor.fetchall()

                if domains:
                    print(f"\n📄 List of domains for program '{program_name}':")
                    for domain in domains:
                        print(f"\033[1m{domain[0]}\033[0m")
                else:
                    print(f"❌ No domains found for program '{program_name}'.")
            else:
                print(f"❌ Program '{program_name}' not found.")
        else:
            print("❌ Please specify a program name to list domains.")

    elif entity_type == 'ip':
        if program_name:
            # Récupérer l'ID du programme en fonction de son nom
            cursor.execute('''
                SELECT id FROM programs WHERE program_name = ?
            ''', (program_name,))
            program = cursor.fetchone()

            if program:
                program_id = program[0]
                # Récupérer les IP associées aux domaines du programme
                cursor.execute('''
                    SELECT DISTINCT domain_details.ip FROM domain_details
                    JOIN domains ON domains.id = domain_details.domain_id
                    WHERE domains.program_id = ? AND domain_details.ip IS NOT NULL
                    ORDER BY domain_details.ip
                ''', (program_id,))
                ips = cursor.fetchall()

                if ips:
                    print(f"\n📄 List of IP addresses for program '{program_name}':")
                    for ip in ips:
                        print(f"\033[1m{ip[0]}\033[0m")
                else:
                    print(f"❌ No IP addresses found for program '{program_name}'.")
            else:
                print(f"❌ Program '{program_name}' not found.")
        else:
            print("❌ Please specify a program name to list IP addresses.")

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

    # Vérifier si des arguments sont passés dans la ligne de commande
    if len(sys.argv) > 1:
        session = PromptSession()
        #print_formatted_text("\n【Welcome to ReconNinja v1.0 by _frHaKtal_】")
        #print_formatted_text("‼️ Press tab for autocompletion and available commands\n")
        lolcat("\n【Welcome to ReconNinja v1.0 by _frHaKtal_】")
        lolcat("‼️ Press tab for autocompletion and available commands\n")

        setup_database()

        program_name = sys.argv[1]
        command_completer = CommandCompleter()

        add_program(program_name)
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
                                print(f"✔️  \033[1m{len(domain_enum.splitlines())}\033[0m domain find")
                            else:
                                domains.append(domain)

                        # Lancer l'ajout des domaines en parallèle
                        #print(len(domains))
                        #print(domains)
                        add_domains_in_parallel_multithread(program_name, domains)
                    elif command == 'show':
                        show(sys.argv[1])
                    elif command == 'search':
                        search(args[0],sys.argv[1])
                    elif command == 'list':
                        if args:
                            list(args[0], sys.argv[1])
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
                        rm(args[1], args[0])
                    elif command == 'exit':
                        print("Exiting...")
                        break
            except (KeyboardInterrupt, EOFError):
                print("Exiting...")
                break
    else:
        # Si aucun argument n'est passé, afficher la liste des programmes
        list('program')

if __name__ == "__main__":
    main()
