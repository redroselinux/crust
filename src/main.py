import base
import os
import time
import subprocess
import custom_commands 
import sys
import cohere
import troubleshooting
import capk
import config_find
import importlib.util
from pathlib import Path
import aur_check
import readline
import ctnp
import cd

pkgs = ""

configs = config_find.find_crust_folder()
if configs == None: configs = "default"; print("warn: configs are set as default")
print(configs)

try:
    file_path = Path(str(configs) + "/aliases.py")

    spec = importlib.util.spec_from_file_location("aliases", file_path)
    aliases = importlib.util.module_from_spec(spec)
    sys.modules["aliases"] = aliases
    spec.loader.exec_module(aliases)
except Exception as e:
    print(f"warn: no aliases were loaded due to an {e} error")

try:
    file_path = Path(str(configs) + "/prompt.py")
    spec = importlib.util.spec_from_file_location("prompt", file_path)
    prompt_module = importlib.util.module_from_spec(spec)
    sys.modules["prompt"] = prompt_module
    spec.loader.exec_module(prompt_module)
except Exception as e:
    print(f"warn: no prompt was loaded due to an {e} error")

"""
# todo: move to .crust
# Try to run any custom startup commands
try:
    custom_commands.main()
except Exception as e:
    pass
"""

# Setup readline history and completion
def setup_readline():
    """Configure readline for command history and tab completion"""
    # Set up history file
    history_file = os.path.expanduser("~/.crust_history")
    
    try:
        # Load existing history
        readline.read_history_file(history_file)
        # Set maximum history length
        readline.set_history_length(1000)
    except FileNotFoundError:
        # History file doesn't exist yet, will be created when we save
        pass
    except Exception as e:
        print(f"Warning: Could not load command history: {e}")
    
    # Set up tab completion
    readline.set_completer(tab_completer)
    readline.parse_and_bind('tab: complete')
    
    # Enable history search with arrow keys
    readline.parse_and_bind('"\\e[A": history-search-backward')
    readline.parse_and_bind('"\\e[B": history-search-forward')
    
    return history_file

def tab_completer(text, state):
    """
    Return successive completion strings for the readline completer.
    
    This function is used as a readline tab-completion callback. On the first call for a given completion attempt (state == 0) it builds a list of candidate completions and caches them on the function as `tab_completer.matches`. Behavior:
    - If completing the first word (no prior words or the cursor is at the end of the first word), it completes command names from a union of built-in and common shell commands.
    - Otherwise it completes filesystem entries. Supports `~` expansion for the home directory, lists the target directory, and matches entries that start with the typed basename. Directory candidates are returned with a trailing os.path.sep.
    - If the target directory cannot be read (permission or OSError), no matches are produced.
    
    Parameters:
        text (str): The current token to complete.
        state (int): The completion index requested by readline (0..n). On first call for a given text this function prepares the candidate list.
    
    Returns:
        str | None: The matching completion string for the requested state, or None when no more matches are available.
    """
    if state == 0:
        # This is the first time for this text, generate matches
        line = readline.get_line_buffer()
        
        # Get current line up to cursor
        begin_idx = readline.get_begidx()
        end_idx = readline.get_endidx()
        
        # Split the line into parts
        words = line[:begin_idx].split()
        
        # Built-in commands that should be completed
        builtin_commands = [
            'ls', 'cd', 'about', 'lsusb', 'disk usage', 'troubleshooting',
            'capk', 'aur_check', '.question', 'ctnp'
        ]
        
        # Common shell commands
        common_commands = [
            'ls', 'cd', 'pwd', 'mkdir', 'rmdir', 'rm', 'cp', 'mv',
            'cat', 'less', 'more', 'head', 'tail', 'grep', 'find',
            'which', 'whereis', 'ps', 'top', 'htop', 'kill', 'killall',
            'chmod', 'chown', 'ln', 'du', 'df', 'free', 'uname',
            'whoami', 'date', 'uptime', 'history', 'clear', 'exit',
            'git', 'python', 'python3', 'pip', 'pip3', 'nano', 'vim',
            'emacs', 'code', 'wget', 'curl', 'ssh', 'scp', 'rsync'
        ]
        
        if len(words) == 0 or (len(words) == 1 and begin_idx == end_idx):
            # Completing the first word (command)
            all_commands = list(set(builtin_commands + common_commands))
            tab_completer.matches = [cmd for cmd in all_commands if cmd.startswith(text)]
        else:
            # Completing arguments (file/directory names)
            if text.startswith('~'):
                # Handle home directory expansion
                path = os.path.expanduser(text)
                prefix = '~'
            else:
                path = text
                prefix = ''
            
            # Get directory path and filename pattern
            if os.path.sep in path:
                dirname = os.path.dirname(path)
                basename = os.path.basename(path)
            else:
                dirname = '.'
                basename = path
            
            try:
                # Get all files and directories matching the pattern
                if dirname:
                    entries = os.listdir(dirname if dirname != '.' else os.getcwd())
                else:
                    entries = os.listdir('.')
                
                matches = []
                for entry in entries:
                    if entry.startswith(basename):
                        full_path = os.path.join(dirname, entry) if dirname != '.' else entry
                        if prefix:
                            full_path = prefix + full_path[len(os.path.expanduser(prefix)):]
                        
                        # Add trailing slash for directories
                        if os.path.isdir(os.path.join(dirname if dirname != '.' else '.', entry)):
                            matches.append(full_path + os.path.sep)
                        else:
                            matches.append(full_path)
                
                tab_completer.matches = matches
            except (OSError, PermissionError):
                # If we can't read the directory, no matches
                tab_completer.matches = []
    
    # Return the next match
    try:
        return tab_completer.matches[state]
    except (AttributeError, IndexError):
        return None

def save_history(history_file):
    """Save command history to file"""
    try:
        readline.write_history_file(history_file)
    except Exception as e:
        print(f"Warning: Could not save command history: {e}")

def main():
    # Initialize readline for history and tab completion
    """
    Run the interactive Crust shell REPL: initialize readline (history and tab completion), display a prompt with VENV and git context, read user input, and dispatch built-in commands, shell commands, alias expansion, and the AI-assisted `.question` flow. The loop handles special built-ins (ls, lsusb, disk usage/df, aur_check, capk, troubleshooting, about, cd, ctnp), supports alias replacement, and falls back to invoking the system shell for other commands.
    """
    history_file = setup_readline()
    
    # Main interactive shell loop
    while True:
        try:
            # I am sorry
            # for now removed, causing problems with dirs
            """with open("./venv_prompt.txt") as f:
                show_venv = f.read()
                if show_venv.strip().lower() != "yes":
                    show_venv = False
            try:
                del show_venv
                show_venv = False
            except NameError:
                show_venv = True"""
            
            try:
                prompt_module.main()
            except Exception:
                print("fallback prompt")
                print(os.getcwd() + " > ", end="")

            # Read user input with readline (supports history and tab completion)
            try:
                prompt = input()
                # Add non-empty commands to history
                if prompt.strip():
                    readline.add_history(prompt)
            except (EOFError, KeyboardInterrupt):
                # Handle Ctrl+D or Ctrl+C
                raise

            # Handle 'ls' command: show directory listing in a table
            if prompt == "ls" or prompt == "ls -l" or prompt == "ls -la":
                table = base.Table(title="󰉋 Directory Listing", show_lines=True)
                table.add_column("󰈔 Name", style="cyan")
                table.add_column("󰊢 Type", style="magenta")
                table.add_column("󰍛 Size", style="green")
                table.add_column("󰥔 Modified", style="yellow")
                try:
                    for entry in os.listdir('.'):
                        entry_path = os.path.join('.', entry)
                        if os.path.isdir(entry_path):
                            entry_type = " Directory"
                            size = "-"
                        else:
                            entry_type = " File"
                            size = f"{os.path.getsize(entry_path)} bytes"
                        modified_time = time.ctime(os.path.getmtime(entry_path))
                        table.add_row(f"{entry}", entry_type, size, modified_time)
                    base.console.print(table)
                except Exception as e:
                    base.console.print(f"󰅚 Error listing directory: {e}", style="bold red")
            elif prompt.startswith("aur_check"):
                pkg = prompt.strip().replace("aur_check ", "")
                aur_check.main(pkg)
            elif prompt == "disk usage" or prompt == "df -h":
                try:
                    output = subprocess.check_output(["df", "-h"], text=True)
                    lines = output.strip().split("\n")
                    headers = lines[0].split()
                    table = base.Table(title="💾 Disk Usage", show_lines=True)
                    for h in headers:
                        table.add_column(h, style="cyan")

                    for line in lines[1:]:
                        table.add_row(*line.split())

                    base.console.print(table)
                except Exception as e:
                    base.console.print(f"[red]Error running df: {e}[/red]")

            elif prompt.startswith("capk"):
                package = prompt.replace("capk ", "")
                capk.search(package)

            elif prompt == "lsusb":
                try:
                    output = subprocess.check_output(["lsusb"], text=True)
                    lines = output.strip().split("\n")

                    # if theres a table existing, remove it
                    try:
                        del table
                    except NameError:
                        pass

                    table = base.Table(title=" USB Devices", show_lines=True)
                    table.add_column("Bus", style="cyan")
                    table.add_column("Device", style="green")
                    table.add_column("ID", style="magenta")
                    table.add_column("Description", style="yellow")

                    for line in lines:
                        parts = line.split()
                        bus = parts[1]
                        device = parts[3].strip(":")
                        usb_id = parts[5]
                        description = " ".join(parts[6:])
                        table.add_row(bus, device, usb_id, description)

                    base.console.print(table)
                except FileNotFoundError:
                    base.console.print("󰍉 'lsusb' not found.", style="bold red")
                except Exception as e:
                    base.console.print(f"󰅚 Error running lsusb: {e}", style="bold red")
            elif prompt == "troubleshooting":
                troubleshooting.run()
            elif prompt == "cd .." and os.getcwd() == "/":
                print("THERE IS NO ESCAPE")
                time.sleep(1)
                os.system("curl ascii.live/rick")
            elif prompt == "about":
                from rich.table import Table as RichTable
                plus_lines = [" + ", "+++", " + "]
                about_lines = [
                    "[bold salmon1]Crust Shell[/]",
                    "Author: Juraj Kollár (mostypc123)",
                    "Version: dev"
                ]
                table = RichTable(show_header=False, box=None, pad_edge=False)
                table.add_column(justify="left", style="bold salmon1")  # icon column
                table.add_column(justify="left", style="bold white")    # info column
                for plus, about in zip(plus_lines, about_lines):
                    table.add_row(plus, about)
                base.console.print(table)
                continue

            elif prompt.startswith("cd"):
                # Extract the directory argument
                if prompt.strip() == "cd":
                    # No argument provided, go to HOME
                    entered_dir = os.path.expanduser("~")
                else:
                    # Extract argument and expand ~ if present
                    arg = prompt[2:].strip()  # Remove 'cd' and strip whitespace
                    entered_dir = os.path.expanduser(arg)
                
                try:
                    os.chdir(entered_dir)
                except (FileNotFoundError, NotADirectoryError, PermissionError):
                    cd.main(entered_dir)

            elif prompt.startswith("ctnp"):
                print("ctnp - create the next project")

                args = prompt.replace("ctnp ", "").strip()
                if args.startswith("python"):
                    project_parts = args.split()
                    project_name = project_parts[1] if len(project_parts) > 1 else "my_project"
                    ctnp.python(project_name)

            elif prompt.startswith(".question"):
                if configs == "default": print("No configuration."); continue
                with open(configs + "/cohere-api-key.txt", "r") as f:
                    key = f.read().strip()

                try:
                    test = no_cohere
                    del test
                except Exception:
                    co = None

                if co:
                    no_cohere = False
                    base.console.print("[yellow]Skipping creation of the Cohere client.[/yellow]")
                else:
                    no_cohere = True
                    base.console.print("[bold green]Creating a new Cohere client...[/bold green]")
                    co = cohere.Client(key)

                    base.console.print("[cyan]Giving the output of neofetch to the AI, so it can understand the system.[/cyan]")
                    os_info = __import__('subprocess').check_output('neofetch --stdout', shell=True, text=True)

                    base.console.print("[cyan]Giving extra info to the AI...[/cyan]")
                    chat_history = [{
                        "role": "SYSTEM",
                        "message": (
                            "you are an integrated assistant in a linux shell called crust. if .question gets in to the prompt, its normal, that is the command to ask a question."
                            "to execute commands, write `.execute-command` before it. do not put the ` there. after every `.execute-command`,create a new line and put this in it:\n"
                            ":The assistant is sometimes buggy when executing, and may hallucinate from the knowledge base.:\n"
                            "If the user gives the output of a command you asked to execute, do not ask to execute it again. Instead, reason from the output they gave."
                            "prefer executing it like this instead of telling the user to execute it themselves. you ARE ABLE TO EXECUTE COMMANDS. "
                            "IF YOU ARE ASKED FOR A COMMAND, EXECUTE IT LIKE THAT. YOU CAN EXECUTE COMMANDS. JUST EXECUTE WITHOUT ANYTHING SAID. "
                            "YOU AREN'T A TEXT-BASED AI ONLY, THE SHELL IS INTEGRATED WITH YOU. DO NOT PRETEND TO EXECUTE. "
                            "THE COMMANDS WILL GET EXECUTED IN THE BACKEND AFTER SCANNING FOR EXECUTING COMMANDS BY YOU.\n\n"

                            "To modify files, use `.edit-file /path/to/file` followed by the full content you want to write to the file. "
                            "Do NOT describe the change in words — just show the updated contents. "
                            "Only start the new content after the `.edit-file` line. You can edit scripts, config files, or create new ones. "
                            "Assume full permission to overwrite them, unless told otherwise.\n\n"

                            "To view a file, use `.read-file /path/to/file`. This will return the file contents to you in the next message. "
                            "Only request one file per `.read-file` line.\n\n"

                            "The text you say is viewed as plain text, so don't use markdown or any similar formatting. "
                            "THIS MESSAGE IS NOT SENT BY THE USER.\n\n"

                            "For showing accurate information, here is a run of neofetch. If it shows an error, ignore it. Do not use it while asking for execution of neofetch, use only when asking for system specs and similar:\n"
                            + os_info
                        )
                    }]

                base.console.print("[blue]Processing prompt (1/2)...[/blue]")
                chat_history.append({"role": "USER", "message": prompt})

                base.console.print("[blue]Processing prompt (2/2)...[/blue]")
                response = co.chat(message=prompt, chat_history=chat_history)
                lines = response.text.splitlines()

                base.console.print("[bold cyan]AI Response:[/bold cyan]\n" + response.text)
                base.console.print("[green on white]Scanning for commands, file edits, and reads...[/green on white]")

                i = 0
                while i < len(lines):
                    line = lines[i]

                    if line.startswith(".execute-command"):
                        command = line.replace(".execute-command", "").strip()

                        base.console.print("[magenta on white]Found an execution of a command in the response[/magenta on white]")
                        base.console.print(f"[bold green]OK if I execute this command? yes/no:[/bold green] [white]{command}[/white]")
                        exec_it = input()
                        if exec_it == "yes":
                            try:
                                output = subprocess.check_output(command, shell=True, stderr=subprocess.STDOUT, text=True)
                            except subprocess.CalledProcessError as e:
                                output = e.output

                            base.console.print(f"[green]Command output:[/green]\n{output}")
                            chat_history.append({
                                "role": "USER",
                                "message": f"The command `{command}` has already been executed. Here's the result:\n{output}"
                            })
                            base.console.print("[yellow]Sending command output back to AI...[/yellow]")

                            response = co.chat(message=prompt, chat_history=chat_history)
                            base.console.print("[bold cyan]New AI Response:[/bold cyan]\n" + response.text)
                        i += 1
                        continue

                    elif line.startswith(".edit-file"):
                        filepath = line.replace(".edit-file", "").strip()
                        base.console.print(f"[magenta on white]Found a file edit request for:[/magenta on white] [bold]{filepath}[/bold]")
                        i += 1
                        file_lines = []

                        while i < len(lines) and not lines[i].startswith("."):
                            file_lines.append(lines[i])
                            i += 1

                        file_content = "\n".join(file_lines)
                        base.console.print(f"[bold green]OK if I overwrite this file? yes/no:[/bold green] [white]{filepath}[/white]")
                        exec_it = input()
                        if exec_it == "yes":
                            with open(filepath, "w") as f:
                                f.write(file_content)
                            base.console.print(f"[green]File {filepath} written.[/green]")
                        continue

                    elif line.startswith(".read-file"):
                        filepath = line.replace(".read-file", "").strip()
                        base.console.print(f"[bold cyan]AI requested to read file:[/bold cyan] {filepath}")
                        try:
                            with open(filepath, "r") as f:
                                file_contents = f.read()
                            base.console.print(f"[green]Sending file contents back to AI...[/green]")

                            chat_history.append({"role": "USER", "message": f"Contents of `{filepath}`:\n{file_contents}"})
                            base.console.print("[yellow]Re-querying AI with file contents...[/yellow]")
                            response = co.chat(message=prompt, chat_history=chat_history)
                            base.console.print("[bold cyan]New AI Response:[/bold cyan]\n" + response.text)
                            break 

                        except Exception as e:
                            base.console.print(f"[red]Could not read file {filepath}: {e}[/red]")
                        i += 1
                        continue

                    i += 1


            # For all other commands, run them in the shell
            if prompt in ["about", "lsusb", "ls", "ls -l", "ls -la", "disk usage", "df -h"] or prompt.startswith(".question") or prompt.startswith("cd") or prompt.startswith("capk ") or prompt.startswith("aur_check") or prompt.startswith("ctnp"):
                continue
            else:
                try:
                    # Check for aliases
                    command_parts = prompt.split()
                    if command_parts:
                        first_command = command_parts[0]
                        # Check if the first command is an alias
                        if hasattr(aliases, first_command):
                            alias_command = getattr(aliases, first_command)
                            # Replace the first part with the alias command
                            command_parts[0] = alias_command
                            prompt = ' '.join(command_parts)
                except Exception as e:
                    print(f"error checking for aliases\n>tip: you likely have no .crust folder in your computer\nmessage: {e}")
                try:
                    result = subprocess.run(["bash", "-c", prompt], text=True)
                     
                    # Check if command failed (non-zero return code)
                    if result.returncode != 0:
                        if result.returncode == 127:
                            with open(configs + "/cmds.py", "r") as f:
                                cmds = f.read()
                            if "car" in cmds:
                                with open("/home/"+os.getlogin()+"/.config/car/packagelist", "r") as f:
                                    pkgs = f.read().splitlines()
                                os.remove("pkgs")
                                if prompt.split()[0] in pkgs:
                                    print(prompt.split()[0] + " was not found, but can be installed with:")
                                    print("     car get " + prompt.split()[0] )
                        try:
                            with open(configs + "/cohere-api-key.txt", "r") as f:
                                key_content = f.read().strip()

                            # Use existing co client if available, otherwise create new one
                            try:
                                if not co:
                                    co = cohere.Client(key_content)
                            except (NameError, AttributeError):
                                co = cohere.Client(key_content)

                            # Get distro name
                            distro = subprocess.run(["cat", "/etc/os-release"], capture_output=True, text=True)

                            fix_prompt = f"""Command '{prompt}' failed with exit code {result.returncode}.

System info: {distro.stdout.strip()}

Fix this command by:
- If package not found: install it with the right package manager (yay/paru for AUR on Arch, apt on Ubuntu, etc.)
- If typo: fix the spelling
- Use sudo when needed
- Only reply with the corrected command, nothing else

Fixed command:"""
                            response = co.chat(
                                    message=fix_prompt,
                                    model="command-r",
                                    max_tokens=50,
                                    temperature=0.1
                                    )

                            fix_command = response.text.strip()
                            print(f"(Enter) {fix_command} (n, Enter) cancel ", end="")
                            fix = input()

                            if fix == "":
                                os.system(f"bash -c \"{fix_command}\"")
                            else:
                                pass
                                
                        except Exception:
                            pass  # Silently fail if no config or error
                    
                except KeyboardInterrupt:
                    base.console.print("\n KeyboardInterrupt detected during command. Returning to prompt...\n", style="bold red")
                except Exception as e:
                    print(f"Error running command: {e}")


        except KeyboardInterrupt:
            # Handle Ctrl+C to exit the shell
            base.console.print("\n KeyboardInterrupt detected. Exiting...\n", style="bold red")
            base.console.file.flush()
            time.sleep(0.1) # Allow time for console to flush
            break
        except EOFError:
            # Handle Ctrl+D to exit the shell
            base.console.print("\n[cyan]Goodbye![/cyan]\n", style="bold")
            break
        except Exception as e:
            # Catch-all for unexpected errors
            base.console.print(f"󰅚 An error occurred: {e}", style="bold red")
            continue
    
    # Save command history before exiting
    save_history(history_file)

if __name__ == "__main__":
    main()
