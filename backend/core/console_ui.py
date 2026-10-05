"""Console du terminal : bannière de démarrage, mise en forme colorée des print() et journal.

installer_console() remplace builtins.print par une version stylée (rich) : les
préfixes connus ([JARVIS], [MIC], [WEB]...) reçoivent un emoji et une couleur.
TeeLogger duplique la sortie console dans data/jarvis_run.log.
"""

import os
import sys

import core.shared as shared


def installer_console():
    """Affiche la bannière et installe le print stylé (appelé tout au début de main.py)."""
    # ── Banner affiché immédiatement avant les imports lourds ──────
    try:
        from rich.console import Console
        from rich.panel import Panel
        from rich.text import Text
        from rich.align import Align
        import builtins
        import re

        console = Console()

        # ── Custom printing wrapper to beautify all console output ──
        _original_print = builtins.print

        def safe_original_print(s, **kwargs):
            try:
                _original_print(s, **kwargs)
            except UnicodeEncodeError:
                try:
                    enc = sys.stdout.encoding or 'utf-8'
                    safe_s = s.encode(enc, errors='replace').decode(enc)
                    _original_print(safe_s, **kwargs)
                except Exception:
                    safe_s = s.encode('ascii', errors='replace').decode('ascii')
                    _original_print(safe_s, **kwargs)

        def custom_print(*args, **kwargs):
            sep = kwargs.get('sep', ' ')
            # Fallback to original print if output target is custom (e.g. file, stderr redirection)
            if kwargs.get('file') is not None:
                safe_original_print(sep.join(str(arg) for arg in args) if args else '', **kwargs)
                return

            msg = sep.join(str(arg) for arg in args)

            # Adjust spacing for double-width emojis in classic Windows conhost
            for emo in ["⏰", "🤖", "🔄", "📱", "👏", "💬", "🌐", "🎙", "🌤", "🗣", "🚀", "⚙", "✔", "❌", "⚠"]:
                if emo in msg:
                    msg = re.sub(re.escape(emo) + r"\s*", emo + "  ", msg)

            # Define log module mapping: prefix -> (emoji, rich color)
            prefixes = {
                "[ALARME]": ("⏰", "cyan"),
                "[JARVIS]": ("🤖", "cyan"),
                "[UPDATE]": ("🔄", "cyan"),
                "[MOBILE]": ("📱", "cyan"),
                "[CLAP]": ("👏", "cyan"),
                "[CONV]": ("💬", "cyan"),
                "[WEB]": ("🌐", "cyan"),
                "[MIC]": ("🎙️", "cyan"),
                "[METEO]": ("🌤️", "cyan"),
                "[TTS LOCAL]": ("🗣️", "cyan"),
                "[SPEECH]": ("🗣️", "cyan"),
                "[DÉMARRAGE]": ("🚀", "cyan"),
                "[INFO]": ("ℹ️", "cyan"),
                "[SPEAKER]": ("🎙️", "cyan"),
                "[BIOMETRICS]": ("🎙️", "cyan"),
                "[VAD]": ("🎙️", "cyan"),
                "[WAKEWORD]": ("🎙️", "cyan"),
                "[AV LIVE]": ("🛡️", "cyan"),
                "[AV]": ("🛡️", "cyan"),
                "[AUDIOSTREAMMANAGER]": ("🔊", "cyan"),
            }

            stripped = msg.lstrip()
            indent = msg[:len(msg) - len(stripped)]

            # Format 1: Text starting with an emoji/symbol followed by a bracketed tag
            # e.g., "✔ [🗣 SPEECH] Parole générée..." or "❌ [🗣 SPEECH] Échec..."
            # Or simple prefix like "[JARVIS] Tentative de lancement..."
            if '[' in stripped and ']' in stripped:
                idx_open = stripped.index('[')
                idx_close = stripped.index(']')
                if idx_open < 10 and idx_close > idx_open:  # tag is near the start
                    prefix_symbol = stripped[:idx_open].strip()
                    tag = stripped[idx_open+1:idx_close]
                    rest = stripped[idx_close+1:].strip()

                    # Format prefix symbol if it has status icons
                    if "✔" in prefix_symbol:
                        prefix_symbol = prefix_symbol.replace("✔", "[bold green]✔[/bold green]")
                    if "⚡" in prefix_symbol:
                        prefix_symbol = prefix_symbol.replace("⚡", "[bold yellow]⚡[/bold yellow]")
                    if "❌" in prefix_symbol:
                        prefix_symbol = prefix_symbol.replace("❌", "[bold red]❌[/bold red]")
                    if "⚠" in prefix_symbol:
                        prefix_symbol = prefix_symbol.replace("⚠", "[bold orange1]⚠[/bold orange1]")

                    tag_upper = f"[{tag.upper()}]"
                    known = False
                    for prefix, (emoji, color) in prefixes.items():
                        if tag_upper == prefix:
                            symbol_to_use = prefix_symbol if prefix_symbol else emoji

                            # Apply inline highlight styling to the rest of the text
                            if "[OK]" in rest:
                                rest = rest.replace("[OK]", "[bold green]✔  OK[/bold green]")
                            if "[KO]" in rest:
                                rest = rest.replace("[KO]", "[bold red]❌  KO[/bold red]")
                            if "✔" in rest:
                                rest = rest.replace("✔", "[bold green]✔  [/bold green]")
                            if "❌" in rest:
                                rest = rest.replace("❌", "[bold red]❌  [/bold red]")
                            if "⚠" in rest:
                                rest = rest.replace("⚠", "[bold orange1]⚠  [/bold orange1]")

                            formatted = f"{indent}[bold {color}]{symbol_to_use}  [{tag}][/bold {color}] {rest}"
                            known = True
                            break

                    if not known:
                        # Generic tag not in our primary map (custom speech/status tag)
                        symbol = f"{prefix_symbol}  " if prefix_symbol else ""

                        if "[OK]" in rest:
                            rest = rest.replace("[OK]", "[bold green]✔  OK[/bold green]")
                        if "[KO]" in rest:
                            rest = rest.replace("[KO]", "[bold red]❌  KO[/bold red]")
                        if "✔" in rest:
                            rest = rest.replace("✔", "[bold green]✔  [/bold green]")
                        if "❌" in rest:
                            rest = rest.replace("❌", "[bold red]❌  [/bold red]")
                        if "⚠" in rest:
                            rest = rest.replace("⚠", "[bold orange1]⚠  [/bold orange1]")

                        formatted = f"{indent}{symbol}[bold grey70][{tag}][/bold grey70] {rest}"

                    try:
                        console.print(formatted, **{k: v for k, v in kwargs.items() if k not in ('sep',)})
                        return
                    except Exception:
                        pass

            # Format 2: Bullet item like "      [3] Microphone (BIRD UM1)"
            if stripped.startswith("[") and "]" in stripped:
                match = re.match(r"^\[(\d+)\]", stripped)
                if match:
                    idx = match.group(1)
                    rest = stripped[len(match.group(0)):].strip()
                    formatted = f"{indent}[bold cyan][{idx}][/bold cyan] {rest}"
                    try:
                        console.print(formatted, **{k: v for k, v in kwargs.items() if k not in ('sep',)})
                        return
                    except Exception:
                        pass
                else:
                    match_generic = re.match(r"^\[([^\]]+)\]", stripped)
                    if match_generic:
                        tag = match_generic.group(1)
                        rest = stripped[len(match_generic.group(0)):].strip()
                        formatted = f"{indent}[bold grey70][{tag}][/bold grey70] {rest}"
                        try:
                            console.print(formatted, **{k: v for k, v in kwargs.items() if k not in ('sep',)})
                            return
                        except Exception:
                            pass

            # Default fallback
            safe_original_print(msg, **kwargs)

        builtins.print = custom_print

        # ── Modern, high-tech initialization header ──
        banner = Text()
        banner.append("J.A.R.V.I.S", style="bold cyan")

        print()
        console.print(Panel(
            Align.center(banner),
            border_style="cyan",
            title="[bold red]SYSTEM INITIALIZATION[/bold red]",
            subtitle="[bold cyan]v9.0[/bold cyan]",
            expand=False,
            padding=(1, 6)
        ))
        console.print("[yellow]⚡  Chargement des modules neuronaux de J.A.R.V.I.S...[/yellow]\n")
    except Exception as e:
        print()
        print("=" * 60)
        print("   J.A.R.V.I.S — Demarrage du systeme")
        print("=" * 60)
        print()
        print("  Chargement des modules en cours...")
        print()


class TeeLogger(object):
    def __init__(self, filename=None):
        if filename is None:
            filename = os.path.join(shared.RACINE_PROJET, "data", "jarvis_run.log")
        self.terminal = sys.stdout
        self.log = open(filename, "w", encoding="utf-8", errors="ignore")
    def write(self, message):
        self.terminal.write(message)
        try:
            self.log.write(message)
            self.log.flush()
        except Exception:
            pass
    def flush(self):
        self.terminal.flush()
        try:
            self.log.flush()
        except Exception:
            pass
