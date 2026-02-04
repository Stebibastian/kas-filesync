#!/usr/bin/env python3
"""
3-Wege-Merge Modul für KAS Filesync.
Ermöglicht Git-ähnliches Mergen von Textdateien.
"""

import difflib
from dataclasses import dataclass
from typing import List, Tuple, Optional


@dataclass
class Conflict:
    """Repräsentiert einen Merge-Konflikt."""
    line_number: int
    base_lines: List[str]
    source_lines: List[str]
    target_lines: List[str]


@dataclass
class MergeResult:
    """Ergebnis eines Merge-Versuchs."""
    success: bool
    content: str
    conflicts: List[Conflict]


def is_text_file(filepath: str) -> bool:
    """Prüft ob eine Datei eine Textdatei ist."""
    text_extensions = {
        '.txt', '.md', '.json', '.yaml', '.yml', '.xml', '.html', '.css', '.js',
        '.py', '.sh', '.bash', '.zsh', '.conf', '.cfg', '.ini', '.toml',
        '.csv', '.tsv', '.log', '.env', '.gitignore', '.dockerignore'
    }
    import os
    _, ext = os.path.splitext(filepath.lower())
    if ext in text_extensions:
        return True

    # Versuche Datei zu lesen und prüfe auf Binär-Zeichen
    try:
        with open(filepath, 'rb') as f:
            chunk = f.read(8192)
            # Null-Bytes deuten auf Binärdatei hin
            if b'\x00' in chunk:
                return False
        return True
    except:
        return False


def three_way_merge(base: str, source: str, target: str) -> MergeResult:
    """
    Führt einen 3-Wege-Merge durch.

    Args:
        base: Inhalt der Base-Version (letzte gemeinsame Version)
        source: Inhalt der Source-Datei (lokale Änderungen)
        target: Inhalt der Target-Datei (remote Änderungen)

    Returns:
        MergeResult mit gemergtem Inhalt und eventuellen Konflikten
    """
    # Wenn source und target gleich sind, kein Merge nötig
    if source == target:
        return MergeResult(success=True, content=source, conflicts=[])

    # Wenn nur eine Seite geändert wurde
    if source == base:
        return MergeResult(success=True, content=target, conflicts=[])
    if target == base:
        return MergeResult(success=True, content=source, conflicts=[])

    # Beide haben Änderungen - echter Merge nötig
    base_lines = base.splitlines(keepends=True)
    source_lines = source.splitlines(keepends=True)
    target_lines = target.splitlines(keepends=True)

    # Sicherstellen dass letzte Zeile mit Newline endet (für konsistenten Vergleich)
    if base_lines and not base_lines[-1].endswith('\n'):
        base_lines[-1] += '\n'
    if source_lines and not source_lines[-1].endswith('\n'):
        source_lines[-1] += '\n'
    if target_lines and not target_lines[-1].endswith('\n'):
        target_lines[-1] += '\n'

    # Diff von Base zu Source und Base zu Target
    source_matcher = difflib.SequenceMatcher(None, base_lines, source_lines)
    target_matcher = difflib.SequenceMatcher(None, base_lines, target_lines)

    # Änderungs-Bereiche sammeln
    source_changes = get_change_ranges(source_matcher)
    target_changes = get_change_ranges(target_matcher)

    # Prüfe auf überlappende Änderungen (Konflikte)
    conflicts = []
    merged_lines = []

    # Verwende diff3-ähnlichen Algorithmus
    merged, conflicts = merge_with_diff3(base_lines, source_lines, target_lines)

    if conflicts:
        return MergeResult(
            success=False,
            content=''.join(merged),
            conflicts=conflicts
        )

    return MergeResult(
        success=True,
        content=''.join(merged),
        conflicts=[]
    )


def get_change_ranges(matcher: difflib.SequenceMatcher) -> List[Tuple[int, int, str]]:
    """Extrahiert geänderte Bereiche aus einem SequenceMatcher."""
    changes = []
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag != 'equal':
            changes.append((i1, i2, tag))
    return changes


def ranges_overlap(r1: Tuple[int, int], r2: Tuple[int, int]) -> bool:
    """Prüft ob zwei Bereiche sich überlappen."""
    return r1[0] < r2[1] and r2[0] < r1[1]


def merge_with_diff3(base: List[str], source: List[str], target: List[str]) -> Tuple[List[str], List[Conflict]]:
    """
    Führt einen diff3-artigen Merge durch.

    Returns:
        Tuple von (gemergten Zeilen, Liste von Konflikten)
    """
    conflicts = []
    result = []

    # Verwende SequenceMatcher für beide Richtungen
    source_ops = list(difflib.SequenceMatcher(None, base, source).get_opcodes())
    target_ops = list(difflib.SequenceMatcher(None, base, target).get_opcodes())

    # Erstelle eine Map der Änderungen pro Base-Zeile
    source_changes = {}  # base_idx -> (new_lines, operation)
    target_changes = {}

    for tag, i1, i2, j1, j2 in source_ops:
        if tag != 'equal':
            for i in range(i1, max(i2, i1 + 1)):
                source_changes[i] = (source[j1:j2] if tag != 'delete' else [], tag, i1, i2, j1, j2)

    for tag, i1, i2, j1, j2 in target_ops:
        if tag != 'equal':
            for i in range(i1, max(i2, i1 + 1)):
                target_changes[i] = (target[j1:j2] if tag != 'delete' else [], tag, i1, i2, j1, j2)

    # Gehe durch Base und wende Änderungen an
    i = 0
    processed_source = set()
    processed_target = set()

    while i < len(base) or i in source_changes or i in target_changes:
        source_change = source_changes.get(i)
        target_change = target_changes.get(i)

        # Überspringe bereits verarbeitete Änderungen
        if source_change and source_change[2] in processed_source:
            source_change = None
        if target_change and target_change[2] in processed_target:
            target_change = None

        if source_change and target_change:
            # Beide haben an dieser Stelle geändert
            s_lines, s_tag, s_i1, s_i2, s_j1, s_j2 = source_change
            t_lines, t_tag, t_i1, t_i2, t_j1, t_j2 = target_change

            # Markiere als verarbeitet
            processed_source.add(s_i1)
            processed_target.add(t_i1)

            # Prüfe ob die Änderungen identisch sind
            if s_lines == t_lines:
                # Gleiche Änderung - einfach übernehmen
                result.extend(s_lines)
            else:
                # Konflikt!
                conflict = Conflict(
                    line_number=i + 1,
                    base_lines=base[s_i1:s_i2] if s_i1 < len(base) else [],
                    source_lines=list(s_lines),
                    target_lines=list(t_lines)
                )
                conflicts.append(conflict)

                # Füge Konflikt-Marker ein
                result.append(f"<<<<<<< SOURCE\n")
                result.extend(s_lines)
                result.append(f"=======\n")
                result.extend(t_lines)
                result.append(f">>>>>>> TARGET\n")

            # Überspringe die verarbeiteten Base-Zeilen
            i = max(s_i2, t_i2)

        elif source_change:
            # Nur Source hat geändert
            s_lines, s_tag, s_i1, s_i2, s_j1, s_j2 = source_change
            processed_source.add(s_i1)
            result.extend(s_lines)
            i = s_i2

        elif target_change:
            # Nur Target hat geändert
            t_lines, t_tag, t_i1, t_i2, t_j1, t_j2 = target_change
            processed_target.add(t_i1)
            result.extend(t_lines)
            i = t_i2

        else:
            # Keine Änderung - Base übernehmen
            if i < len(base):
                result.append(base[i])
            i += 1

    return result, conflicts


def format_conflict_for_display(conflict: Conflict) -> str:
    """Formatiert einen Konflikt für die Anzeige."""
    lines = []
    lines.append(f"Zeile {conflict.line_number}:")
    lines.append("  Base:")
    for line in conflict.base_lines:
        lines.append(f"    {line.rstrip()}")
    lines.append("  Source (lokal):")
    for line in conflict.source_lines:
        lines.append(f"    {line.rstrip()}")
    lines.append("  Target (remote):")
    for line in conflict.target_lines:
        lines.append(f"    {line.rstrip()}")
    return '\n'.join(lines)


def resolve_conflict_with_source(content: str) -> str:
    """Löst alle Konflikte zugunsten von Source auf."""
    lines = content.splitlines(keepends=True)
    result = []
    in_conflict = False
    in_source = False

    for line in lines:
        if line.startswith('<<<<<<< SOURCE'):
            in_conflict = True
            in_source = True
        elif line.startswith('=======') and in_conflict:
            in_source = False
        elif line.startswith('>>>>>>> TARGET'):
            in_conflict = False
        elif in_conflict and in_source:
            result.append(line)
        elif not in_conflict:
            result.append(line)

    return ''.join(result)


def resolve_conflict_with_target(content: str) -> str:
    """Löst alle Konflikte zugunsten von Target auf."""
    lines = content.splitlines(keepends=True)
    result = []
    in_conflict = False
    in_target = False

    for line in lines:
        if line.startswith('<<<<<<< SOURCE'):
            in_conflict = True
        elif line.startswith('=======') and in_conflict:
            in_target = True
        elif line.startswith('>>>>>>> TARGET'):
            in_conflict = False
            in_target = False
        elif in_conflict and in_target:
            result.append(line)
        elif not in_conflict:
            result.append(line)

    return ''.join(result)


def has_conflict_markers(content: str) -> bool:
    """Prüft ob der Inhalt noch Konflikt-Marker enthält."""
    return '<<<<<<< SOURCE' in content or '>>>>>>> TARGET' in content


if __name__ == '__main__':
    # Test
    base = """Zeile 1
Zeile 2
Zeile 3
Zeile 4
Zeile 5
"""

    source = """Zeile 1 - geändert von Source
Zeile 2
Zeile 3
Zeile 4
Zeile 5
"""

    target = """Zeile 1
Zeile 2
Zeile 3 - geändert von Target
Zeile 4
Zeile 5
"""

    result = three_way_merge(base, source, target)
    print(f"Erfolg: {result.success}")
    print(f"Konflikte: {len(result.conflicts)}")
    print("Ergebnis:")
    print(result.content)
