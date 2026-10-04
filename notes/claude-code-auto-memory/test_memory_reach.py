#!/usr/bin/env python3
# From https://houseofvibe.ai/blog/claude-code-auto-memory
"""Tests for memory_reach.py. Each test builds its own folder under a temp dir.

    python3 test_memory_reach.py            # all tests
    python3 test_memory_reach.py -k crlf    # a subset
"""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).with_name("memory_reach.py")
POINTER = ("- [Archive tier](memory-archive-index.md): {n} older notes not listed here, one line each; "
           "open it when an older topic, a past decision, or a note name comes up\n")


def run(*args, env=None):
    p = subprocess.run([sys.executable, str(SCRIPT), *map(str, args)], capture_output=True, env=env)
    return p.returncode, p.stdout.decode("utf-8", "replace"), p.stderr.decode("utf-8", "replace")


def load():
    """The script as a module, so a test can wrap one of its functions."""
    import importlib.util
    spec = importlib.util.spec_from_file_location("mr", SCRIPT)
    mr = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mr)
    return mr


def fm(desc_line):
    return f"---\nname: x\n{desc_line}\nmetadata:\n  type: project\n---\n\nBody.\n"


def unreachable(out):
    for line in out.splitlines():
        if "NOT within two steps" in line:
            return int(line.split(":")[1].split("(")[0])
    raise AssertionError(out)


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="mr-test-")
        self.d = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def write(self, name, data):
        p = self.d / name
        p.write_bytes(data if isinstance(data, bytes) else data.encode())
        return p

    def notes(self, *names, desc='description: "a note"'):
        for n in names:
            self.write(n, fm(desc))

    def backups(self, prefix):
        return sorted(p.name for p in self.d.iterdir() if p.name.startswith(prefix + ".bak-"))


class CheckTests(Base):
    def test_cut_and_planted_cases(self):
        lines = ["# Memory\n", "\n", "- [Sub](note-sub.md) lists more\n", "- [Early](note-early.md)\n"]
        lines += [f"- filler {i}\n" for i in range(len(lines), 229)]
        lines += ["- [Late](note-late.md) past the cut\n"]
        lines += [f"- filler {i}\n" for i in range(len(lines), 250)]
        self.write("MEMORY.md", "".join(lines))
        self.write("note-sub.md", fm('description: "sub"') + "\nSee [hop](note-hop.md).\n")
        self.notes("note-early.md", "note-hop.md", "note-late.md", "note-orphan.md")
        code, out, _ = run("check", self.d, "--show", "20")
        self.assertEqual(code, 1)
        self.assertIn("50 line(s) past the load cut", out)
        self.assertEqual(unreachable(out), 2)
        self.assertIn("named by a file the index names: 1", out)
        self.assertIn("- note-late.md", out)
        self.assertIn("- note-orphan.md", out)

    def test_substring_name_does_not_count(self):
        self.write("MEMORY.md", "# M\n\n- [Longer](my-trap.md) a longer filename\n")
        self.notes("my-trap.md", "trap.md")
        code, out, _ = run("check", self.d, "--show", "5")
        self.assertEqual(unreachable(out), 1)
        self.assertIn("- trap.md", out)

    def test_plain_words_and_urls_do_not_count(self):
        self.write("MEMORY.md", "# M\n\nKeep notes short. Add todo items when feedback arrives.\n"
                                "See https://example.com/foo.md and release.notes.md and c++.md\n")
        self.notes("notes.md", "todo.md", "feedback.md", "foo.md", "release.md", "c.md")
        _, out, _ = run("check", self.d)
        self.assertEqual(unreachable(out), 6)

    def test_hyphenated_slug_and_wikilink_count(self):
        self.write("MEMORY.md", "# M\n\nSee deploy-checklist and [[todo]].\n")
        self.notes("deploy-checklist.md", "todo.md")
        code, out, _ = run("check", self.d)
        self.assertEqual((code, unreachable(out)), (0, 0))

    def test_crlf_bytes_are_measured_truthfully(self):
        filler = "x" * 129
        body = "".join(f"- {filler}\r\n" for _ in range(189)) + "- [Z](zed.md)\r\n"
        self.write("MEMORY.md", body.encode())
        self.notes("zed.md")
        self.assertGreater(len(body.encode()), 25_000)
        self.assertLess(len(body.replace("\r\n", "\n").encode()), 25_000)
        _, out, _ = run("check", self.d)
        self.assertEqual(unreachable(out), 1)

    def test_invalid_utf8_does_not_inflate_size(self):
        line = b"- " + b"\xff" * 12 + b" filler" + b"\n"
        data = b"# M\n" + line * 188 + b"- [Z](zed.md)\n"
        self.write("MEMORY.md", data)
        self.notes("zed.md")
        self.assertLess(len(data), 25_000)
        code, out, _ = run("check", self.d)
        self.assertEqual((code, unreachable(out)), (0, 0))

    def test_name_cut_in_half_by_byte_limit(self):
        body = "".join("p" * 129 + "\n" for _ in range(192))      # 24,960 bytes
        body += "q" * 34 + " foo-bar.md\n"                        # 'foo-b' ends at byte 25,000
        self.assertEqual(body.encode().index(b"foo-bar.md"), 24_995)
        self.write("MEMORY.md", body)
        self.notes("foo.md", "foo-bar.md")
        _, out, _ = run("check", self.d)
        self.assertEqual(unreachable(out), 2)

    def test_frontmatter_and_block_comments_are_not_measured(self):
        comment = "<!--\n" + "".join(f"maintainer note {i}\n" for i in range(60)) + "-->\n"
        lines = "".join(f"- filler {i}\n" for i in range(150))
        self.write("MEMORY.md", "---\ntitle: x\n---\n# M\n" + comment + lines + "- [Late](late-note.md)\n")
        self.notes("late-note.md")
        code, out, _ = run("check", self.d)
        self.assertEqual((code, unreachable(out)), (0, 0))

    def test_form_feed_is_not_a_line_break(self):
        self.write("MEMORY.md", "# M\n" + "".join(f"- a\x0cb {i}\n" for i in range(150)) + "- [Z](zed.md)\n")
        self.notes("zed.md")
        code, out, _ = run("check", self.d)
        self.assertEqual((code, unreachable(out)), (0, 0))

    def test_symlink_and_directory_named_md_are_ignored(self):
        self.write("MEMORY.md", "# M\n\n- [A](a.md) and adir.md\n")
        self.notes("a.md")
        (self.d / "adir.md").mkdir()
        os.symlink(self.d / "missing.md", self.d / "dangling.md")
        code, out, err = run("check", self.d)
        self.assertEqual(code, 0, err)
        code, out, err = run("archive", self.d, "--apply")
        self.assertEqual(code, 0, err)

    def test_missing_memory_md(self):
        code, _, err = run("check", self.d)
        self.assertEqual(code, 2)
        self.assertIn("no MEMORY.md", err)


class ArchiveTests(Base):
    def basic(self):
        self.write("MEMORY.md", "# Memory\n\n- [Kept](kept-note.md) a curated line\n")
        self.notes("kept-note.md")
        self.notes("old-one.md", desc='description: "an older lesson"')
        self.notes("old-two.md", desc="description: >-\n  folded text\n  over two lines")

    def test_preview_changes_nothing(self):
        self.basic()
        before = sorted(p.name for p in self.d.iterdir())
        code, out, _ = run("archive", self.d)
        self.assertEqual(code, 0)
        self.assertIn("preview only", out)
        self.assertEqual(before, sorted(p.name for p in self.d.iterdir()))

    def test_apply_adds_one_line_and_reaches_everything(self):
        self.basic()
        orig = (self.d / "MEMORY.md").read_bytes()
        code, _, err = run("archive", self.d, "--apply")
        self.assertEqual(code, 0, err)
        new = (self.d / "MEMORY.md").read_bytes()
        self.assertEqual(new.splitlines()[2][:24], b"- [Archive tier](memory-")
        self.assertEqual([l for l in new.splitlines(keepends=True) if b"Archive tier" not in l],
                         orig.splitlines(keepends=True))
        arch = (self.d / "memory-archive-index.md").read_text()
        self.assertIn("(old-one.md): an older lesson", arch)
        self.assertIn("(old-two.md): folded text over two lines", arch)
        self.assertNotIn("(kept-note.md)", arch)
        self.assertEqual(self.backups("MEMORY.md").__len__(), 1)
        code, out, _ = run("check", self.d)
        self.assertEqual((code, unreachable(out)), (0, 0))

    def test_second_apply_is_a_no_op(self):
        self.basic()
        run("archive", self.d, "--apply")
        m, a = (self.d / "MEMORY.md").read_bytes(), (self.d / "memory-archive-index.md").read_bytes()
        code, out, _ = run("archive", self.d, "--apply")
        self.assertEqual(code, 0)
        self.assertIn("already up to date", out)
        self.assertEqual((m, a), ((self.d / "MEMORY.md").read_bytes(), (self.d / "memory-archive-index.md").read_bytes()))

    def test_changed_index_gets_a_new_mtime(self):
        self.basic()
        os.utime(self.d / "MEMORY.md", ns=(1_700_000_000_123_456_789,) * 2)
        run("archive", self.d, "--apply")
        self.assertNotEqual((self.d / "MEMORY.md").stat().st_mtime_ns, 1_700_000_000_123_456_789)

    def test_crlf_and_invalid_bytes_preserved(self):
        self.write("MEMORY.md", b"# Memory\r\n\r\n- [A](a-note.md) caf\xe9 \xff bytes\r\n")
        self.notes("a-note.md", "b-note.md")
        run("archive", self.d, "--apply")
        new = (self.d / "MEMORY.md").read_bytes()
        self.assertIn(b"- [A](a-note.md) caf\xe9 \xff bytes\r\n", new)
        self.assertEqual(new.count(b"\r\n"), 4)
        self.assertNotIn(b"\n", new.replace(b"\r\n", b""))

    def test_one_line_file_without_newline(self):
        self.write("MEMORY.md", "# Memory")
        self.notes("a-note.md")
        run("archive", self.d, "--apply")
        lines = (self.d / "MEMORY.md").read_bytes().split(b"\n")
        self.assertEqual(lines[0], b"# Memory")
        self.assertTrue(lines[1].startswith(b"- [Archive tier]"))

    def test_pointer_past_the_cut_is_moved_into_view(self):
        lines = ["# Memory\n"] + [f"- filler {i}\n" for i in range(249)]
        lines.append(POINTER.format(n=3))
        self.write("MEMORY.md", "".join(lines))
        self.notes("x-one.md", "x-two.md")
        code, _, err = run("archive", self.d, "--apply")
        self.assertEqual(code, 0, err)
        new = (self.d / "MEMORY.md").read_text().splitlines()
        self.assertTrue(new[1].startswith("- [Archive tier]"))
        self.assertEqual(sum("Archive tier" in l for l in new), 1)
        code, out, _ = run("check", self.d)
        self.assertEqual((code, unreachable(out)), (0, 0))

    def test_foreign_archive_is_refused_then_backed_up_with_force(self):
        self.write("MEMORY.md", "# M\n\n- [Archive tier](memory-archive-index.md) - 430 pointers, curated by hand\n")
        self.write("memory-archive-index.md", "- [b](b-note.md) - HAND CURATED\n")
        self.notes("b-note.md", "c-note.md")
        code, _, err = run("archive", self.d, "--apply")
        self.assertEqual(code, 2)
        self.assertIn("refusing", err)
        self.assertIn(b"HAND CURATED", (self.d / "memory-archive-index.md").read_bytes())
        code, _, err = run("archive", self.d, "--apply", "--force")
        self.assertEqual(code, 0, err)
        self.assertEqual(len(self.backups("memory-archive-index.md")), 1)
        self.assertIn(b"curated by hand", (self.d / "MEMORY.md").read_bytes())

    def test_stale_backup_is_never_overwritten(self):
        self.basic()
        self.write("MEMORY.md.bak", "OLD unrelated backup\n")
        run("archive", self.d, "--apply")
        self.assertEqual((self.d / "MEMORY.md.bak").read_text(), "OLD unrelated backup\n")
        self.assertEqual(len(self.backups("MEMORY.md")), 1)

    def test_everything_listed_is_a_no_op(self):
        self.write("MEMORY.md", "# M\n\n- [A](a-note.md)\n- [B](b-note.md)\n")
        self.notes("a-note.md", "b-note.md")
        code, out, _ = run("archive", self.d, "--apply")
        self.assertEqual(code, 0)
        self.assertIn("nothing to archive", out)
        self.assertFalse((self.d / "memory-archive-index.md").exists())

    def test_line_200_note_pushed_past_cut_is_archived(self):
        lines = ["# Memory\n"] + [f"- filler {i}\n" for i in range(198)] + ["- [Edge](edge-note.md)\n"]
        self.write("MEMORY.md", "".join(lines))
        self.notes("edge-note.md")
        run("archive", self.d, "--apply")
        self.assertIn("(edge-note.md)", (self.d / "memory-archive-index.md").read_text())
        code, out, _ = run("check", self.d)
        self.assertEqual((code, unreachable(out)), (0, 0))

    def test_archive_description_mention_does_not_count_as_listing(self):
        self.basic()
        self.notes("old-three.md", desc='description: "supersedes (new-note.md) entirely"')
        run("archive", self.d, "--apply")
        self.notes("new-note.md")
        code, out, _ = run("check", self.d, "--show", "5")
        self.assertEqual(unreachable(out), 1)
        self.assertIn("- new-note.md", out)

    def test_description_parsing(self):
        cases = {
            "fold.md": ("description: >\n  folded\n  text", "folded text"),
            "lit.md": ("description: |-\n  literal\n  text", "literal text"),
            "dq.md": ('description: "He said \\"yes\\""', 'He said "yes"'),
            "sq.md": ("description: 'it''s fine'", "it's fine"),
            "wrap.md": ('description: "first line of a quoted\n  value"', "first line of a quoted value"),
            "plain.md": ("description: He said \"yes\"", 'He said "yes"'),
            "hash.md": ('description: "Shipped as PR #123"', "Shipped as PR #123"),
            "colon.md": ("description: key: value: more", "key: value: more"),
        }
        self.write("MEMORY.md", "# M\n")
        for name, (line, _) in cases.items():
            self.write(name, fm(line))
        self.write("bom.md", "﻿" + fm('description: "with a BOM"'))
        self.write("nofm.md", "# Title\n\nFirst prose line.\n")
        run("archive", self.d, "--apply")
        arch = (self.d / "memory-archive-index.md").read_text()
        for name, (_, want) in cases.items():
            self.assertIn(f"({name}): {want}\n", arch, name)
        self.assertIn("(bom.md): with a BOM\n", arch)
        self.assertIn("(nofm.md): First prose line.\n", arch)

    def test_read_only_index_changes_nothing(self):
        self.basic()
        os.chmod(self.d / "MEMORY.md", 0o444)
        try:
            code, _, err = run("archive", self.d, "--apply")
        finally:
            os.chmod(self.d / "MEMORY.md", 0o644)
        if os.geteuid() == 0:
            self.skipTest("root ignores file permissions")
        self.assertEqual(code, 2, err)
        self.assertFalse((self.d / "memory-archive-index.md").exists())


class SafetyTests(Base):
    """Round-2 findings: every one of these lost or rewrote user content before."""

    def basic(self):
        self.write("MEMORY.md", "# Memory\n\n- [Kept](kept-note.md) hand curated line\n- important user line\n")
        self.notes("kept-note.md", "old-one.md")

    def test_same_second_reruns_keep_every_backup(self):
        self.basic()
        orig = (self.d / "MEMORY.md").read_bytes()
        run("archive", self.d, "--apply")
        self.notes("old-two.md")
        run("archive", self.d, "--apply")
        backups = [self.d / n for n in self.backups("MEMORY.md")]
        self.assertTrue(any(b.read_bytes() == orig for b in backups), [b.name for b in backups])

    def test_concurrent_edit_is_not_lost(self):
        import importlib.util
        spec = importlib.util.spec_from_file_location("mr", SCRIPT)
        mr = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mr)
        self.basic()
        real = mr.description

        def racing(p, *a, **k):
            with open(self.d / "MEMORY.md", "ab") as f:
                f.write(b"- [Concurrent](c-new.md) added by a live session\n")
            mr.description = real
            return real(p, *a, **k)

        mr.description = racing
        code = mr.cmd_archive(self.d, True, False)
        self.assertEqual(code, 2)
        self.assertIn(b"added by a live session", (self.d / "MEMORY.md").read_bytes())

    def test_symlinked_index_stays_a_symlink_and_keeps_mode(self):
        real_dir = self.d / "elsewhere"
        real_dir.mkdir()
        target = real_dir / "real-MEMORY.md"
        target.write_text("# M\n\n- [A](a-note.md)\n")
        os.chmod(target, 0o600)
        os.symlink(target, self.d / "MEMORY.md")
        self.notes("a-note.md", "b-note.md")
        code, _, err = run("archive", self.d, "--apply")
        self.assertEqual(code, 0, err)
        self.assertTrue((self.d / "MEMORY.md").is_symlink())
        self.assertIn(b"Archive tier", target.read_bytes())
        self.assertEqual(target.stat().st_mode & 0o777, 0o600)

    def test_hard_link_is_kept(self):
        self.write("MEMORY.md", "# M\n\n- [A](a-note.md)\n")
        os.link(self.d / "MEMORY.md", self.d / "other-link")
        self.notes("a-note.md", "b-note.md")
        run("archive", self.d, "--apply")
        self.assertEqual((self.d / "MEMORY.md").read_bytes(), (self.d / "other-link").read_bytes())

    def test_hand_written_lookalike_line_is_untouched(self):
        hand = ("- [Archive tier](memory-archive-index.md): 12 older notes not listed here "
                "— curated by Will, see also workflow X\n")
        self.write("MEMORY.md", "# M\n\n" + hand + "- [A](a-note.md)\n")
        self.notes("a-note.md", "b-note.md")
        run("archive", self.d, "--apply", "--force")
        self.assertIn(hand.encode(), (self.d / "MEMORY.md").read_bytes())

    def test_pointer_inside_a_comment_is_left_alone(self):
        body = "# M\n<!--\n" + POINTER.format(n=4) + "-->\n- [A](a-note.md)\n"
        self.write("MEMORY.md", body)
        self.notes("a-note.md", "b-note.md")
        run("archive", self.d, "--apply")
        self.assertIn(("<!--\n" + POINTER.format(n=4) + "-->\n").encode(), (self.d / "MEMORY.md").read_bytes())

    def test_comment_followed_by_text_is_not_stripped(self):
        self.write("MEMORY.md", "# Memory\n<!-- a --> real text one\n- [Late](late-note.md)\n"
                                "<!-- b -->\n- [Other](other-note.md)\n")
        self.notes("late-note.md", "other-note.md")
        code, out, _ = run("check", self.d)
        self.assertEqual((code, unreachable(out)), (0, 0))
        self.assertIn("4 lines", out)

    def test_comments_inside_code_fences_count(self):
        fence = "```\n<!--\n" + "".join(f"line {i}\n" for i in range(150)) + "-->\n```\n"
        self.write("MEMORY.md", "# M\n" + fence + "".join(f"- f{i}\n" for i in range(60)) + "- [Late](late-note.md)\n")
        self.notes("late-note.md")
        _, out, _ = run("check", self.d)
        self.assertEqual(unreachable(out), 1)

    def test_marker_must_be_the_first_line(self):
        self.write("MEMORY.md", "# M\n\n- [A](a-note.md)\n")
        self.write("memory-archive-index.md", "# my archive\n- [b](b-note.md) HAND CURATED "
                                              "<!-- generated by memory_reach.py --> marker text\n")
        self.notes("a-note.md", "b-note.md")
        code, _, _ = run("archive", self.d, "--apply")
        self.assertEqual(code, 2)
        self.assertIn(b"HAND CURATED", (self.d / "memory-archive-index.md").read_bytes())

    def test_bom_stays_at_the_start(self):
        self.write("MEMORY.md", b"\xef\xbb\xbf# Memory\n\n- [A](a-note.md)\n")
        self.notes("a-note.md", "b-note.md")
        run("archive", self.d, "--apply")
        new = (self.d / "MEMORY.md").read_bytes()
        self.assertTrue(new.startswith(b"\xef\xbb\xbf# Memory\n"))
        self.assertEqual(new.count(b"\xef\xbb\xbf"), 1)
        run("archive", self.d, "--apply")
        self.assertEqual((self.d / "MEMORY.md").read_bytes().count(b"Archive tier"), 1)

    def test_bom_pointer_only_file_is_not_duplicated(self):
        self.write("MEMORY.md", b"\xef\xbb\xbf" + POINTER.format(n=1).encode())
        self.notes("a-note.md")
        run("archive", self.d, "--apply")
        new = (self.d / "MEMORY.md").read_bytes()
        self.assertEqual(new.count(b"Archive tier"), 1)
        self.assertTrue(new.startswith(b"\xef\xbb\xbf- [Archive tier]"))

    def test_mixed_endings_use_the_neighbouring_line_ending(self):
        self.write("MEMORY.md", b"# M\n\n- [A](a-note.md)\n- crlf line\r\n- tail\n")
        self.notes("a-note.md", "b-note.md")
        run("archive", self.d, "--apply")
        new = (self.d / "MEMORY.md").read_bytes()
        self.assertIn(b"comes up\n- [A]", new)
        self.assertIn(b"- crlf line\r\n", new)

    def test_duplicate_pointers_collapse_to_one(self):
        self.write("MEMORY.md", "# M\n\n" + POINTER.format(n=7) + "- [A](a-note.md)\n" + POINTER.format(n=9))
        self.notes("a-note.md", "b-note.md")
        run("archive", self.d, "--apply")
        new = (self.d / "MEMORY.md").read_text()
        self.assertEqual(new.count("Archive tier"), 1)
        self.assertIn("1 older note not listed", new)

    def test_worst_case_sizing_keeps_a_note_in_view(self):
        ptr = POINTER.format(n=1).replace("1 older notes", "1 older note")
        filler_line = "- " + "f" * 158 + "\n"
        lines = ["# M\n", "\n", ptr]
        tail = "- [X](x-note.md)\n"
        while sum(len(l.encode()) for l in lines) + len(filler_line) + len(tail) <= 25_000:
            lines.append(filler_line)
        pad = 25_000 - sum(len(l.encode()) for l in lines) - len(tail)
        if pad > 3:
            lines.append("-" + "g" * (pad - 2) + "\n")
        lines.append(tail)
        self.write("MEMORY.md", "".join(lines))
        self.assertEqual((self.d / "MEMORY.md").stat().st_size, 25_000)
        self.notes("x-note.md")
        run("archive", self.d, "--apply")
        code, out, _ = run("check", self.d)
        self.assertEqual((code, unreachable(out)), (0, 0))

    def test_odd_filenames_are_listed_and_recognised(self):
        self.write("MEMORY.md", "# M\n")
        for name in ["my note.md", "w(1).md", "(p).md", "x[1].md", "q]r.md"]:
            self.write(name, fm('description: "odd"'))
        code, _, err = run("archive", self.d, "--apply")
        self.assertEqual(code, 0, err)
        code, out, _ = run("check", self.d)
        self.assertEqual((code, unreachable(out)), (0, 0))

    def test_relative_path_mentions_count(self):
        self.write("MEMORY.md", "# M\n- [A](./a-note.md)\n- see memory/b-note.md\n- ~/x/d-note.md\n"
                                "- C:\\Users\\me\\memory\\e-note.md\n")
        self.notes("a-note.md", "b-note.md", "d-note.md", "e-note.md")
        code, out, _ = run("check", self.d)
        self.assertEqual((code, unreachable(out)), (0, 0))

    def test_more_description_forms(self):
        self.write("MEMORY.md", "# M\n")
        self.write("plain2.md", fm("description: first line of plain\n  continued scalar"))
        self.write("esc.md", fm('description: "tab\\there \\u2014 dash"'))
        run("archive", self.d, "--apply")
        arch = (self.d / "memory-archive-index.md").read_text()
        self.assertIn("(plain2.md): first line of plain continued scalar\n", arch)
        self.assertIn("(esc.md): tab here \u2014 dash\n", arch)  # YAML \t is a tab, then "here"

    def test_force_on_a_directory_fails_cleanly(self):
        self.write("MEMORY.md", "# M\n")
        self.notes("a-note.md")
        (self.d / "memory-archive-index.md").mkdir()
        code, _, err = run("archive", self.d, "--apply", "--force")
        self.assertEqual(code, 2)
        self.assertNotIn("Traceback", err)

    def test_unencodable_names_do_not_crash_output(self):
        self.write("MEMORY.md", "# M\n")
        try:
            self.write(os.fsdecode(b"bad\xffname.md"), fm('description: "x"'))
        except (OSError, UnicodeError):
            self.skipTest("filesystem rejects non-UTF-8 names")
        self.notes("日本-note.md")
        env = dict(os.environ, PYTHONIOENCODING="ascii")
        p = subprocess.run([sys.executable, str(SCRIPT), "check", str(self.d)], capture_output=True, env=env)
        self.assertNotIn(b"Traceback", p.stderr)
        p = subprocess.run([sys.executable, str(SCRIPT), "archive", str(self.d)], capture_output=True, env=env)
        self.assertNotIn(b"Traceback", p.stderr)
        run("archive", self.d, "--apply")
        code, out, _ = run("check", self.d)
        self.assertEqual((code, unreachable(out)), (0, 0))

    def test_three_thousand_notes_run_quickly(self):
        import time as _t
        self.write("MEMORY.md", "# M\n" + "".join(f"- [n{i}](note-{i}.md)\n" for i in range(150)))
        for i in range(3000):
            self.write(f"note-{i}.md", fm(f'description: "note {i}"') + "x" * 2000 + "\n")
        t0 = _t.time()
        code, out, err = run("check", self.d)
        self.assertEqual(code, 1, err)
        self.assertEqual(unreachable(out), 2850)
        code, out, err = run("archive", self.d, "--apply")
        self.assertEqual(code, 0, err)
        self.assertEqual((self.d / "memory-archive-index.md").read_text().count("\n- ["), 2850)
        self.assertLess(_t.time() - t0, 30)


class Round3Tests(Base):
    """Round-3 findings."""

    def test_own_archive_keeps_symlink_and_mode_on_refresh(self):
        self.write("MEMORY.md", "# M\n\n- [A](a-note.md)\n")
        self.notes("a-note.md", "b-note.md")
        run("archive", self.d, "--apply")
        real_dir = self.d / "elsewhere"
        real_dir.mkdir()
        real = real_dir / "archive-real.md"
        os.replace(self.d / "memory-archive-index.md", real)
        os.chmod(real, 0o600)
        os.symlink(real, self.d / "memory-archive-index.md")
        self.notes("c-note.md")
        code, _, err = run("archive", self.d, "--apply")
        self.assertEqual(code, 0, err)
        self.assertTrue((self.d / "memory-archive-index.md").is_symlink())
        self.assertIn(b"(c-note.md)", real.read_bytes())
        self.assertEqual(real.stat().st_mode & 0o777, 0o600)

    def test_symlink_into_read_only_dir_changes_nothing(self):
        if os.geteuid() == 0:
            self.skipTest("root ignores permissions")
        ro = self.d / "ro"
        ro.mkdir()
        (ro / "real.md").write_text("# M\n\n- [A](a-note.md)\n")
        os.symlink(ro / "real.md", self.d / "MEMORY.md")
        self.notes("a-note.md", "b-note.md")
        os.chmod(ro, 0o555)
        try:
            code, _, err = run("archive", self.d, "--apply")
        finally:
            os.chmod(ro, 0o755)
        self.assertEqual(code, 2, err)
        self.assertFalse((self.d / "memory-archive-index.md").exists())
        self.assertNotIn(b"Archive tier", (ro / "real.md").read_bytes())

    def test_bom_does_not_change_comment_measurement(self):
        comment = "<!--\n" + "".join(f"note {i}\n" for i in range(150)) + "-->\n"
        rest = "# M\n" + "".join(f"- f{i}\n" for i in range(60)) + "- [Late](late-note.md)\n"
        self.notes("late-note.md")
        outs = []
        for prefix in (b"", b"\xef\xbb\xbf"):
            self.write("MEMORY.md", prefix + (comment + rest).encode())
            outs.append(run("check", self.d)[1].splitlines()[1])
        self.assertEqual(outs[0], outs[1])

    def test_pointer_refresh_at_byte_boundary_stays_visible(self):
        ptr9 = POINTER.format(n=9)
        filler = "- " + "f" * 98 + "\n"
        lines = ["# M\n", "\n"]
        while sum(len(l) for l in lines) + len(filler) + len(ptr9) <= 25_000:
            lines.append(filler)
        pad = 25_000 - sum(len(l) for l in lines) - len(ptr9)
        if pad >= 2:
            lines.append("-" * (pad - 1) + "\n")
        lines.append(ptr9)
        self.write("MEMORY.md", "".join(lines))
        self.assertEqual((self.d / "MEMORY.md").stat().st_size, 25_000)
        for i in range(10):
            self.notes(f"z{i}-note.md")
        code, _, err = run("archive", self.d, "--apply")
        self.assertEqual(code, 0, err)
        code, out, _ = run("check", self.d)
        self.assertEqual((code, unreachable(out)), (0, 0))
        m = (self.d / "MEMORY.md").read_bytes()
        run("archive", self.d, "--apply")
        self.assertEqual(m, (self.d / "MEMORY.md").read_bytes())

    def test_hidden_pointer_only_means_nothing_to_archive(self):
        self.write("MEMORY.md", "# M\n<!--\n" + POINTER.format(n=4) + "-->\n- [A](a-note.md)\n")
        self.notes("a-note.md")
        code, out, _ = run("archive", self.d, "--apply")
        self.assertEqual(code, 0)
        self.assertIn("nothing to archive", out)
        self.assertFalse((self.d / "memory-archive-index.md").exists())

    def fenced(self, opener, inner, closer):
        body = ("# M\n" + opener + "\n" + inner + "<!--\n" + "".join(f"l{i}\n" for i in range(150))
                + "-->\n" + closer + "\n" + "".join(f"- f{i}\n" for i in range(60)) + "- [Late](late-note.md)\n")
        self.write("MEMORY.md", body)
        self.notes("late-note.md")
        return unreachable(run("check", self.d)[1])

    def test_fence_matching_follows_markdown(self):
        self.assertEqual(self.fenced("~~~", "```\n", "~~~"), 1)       # ``` does not close a ~~~ fence
        self.assertEqual(self.fenced("````md", "```\n", "````"), 1)   # shorter fence does not close
        self.assertEqual(self.fenced("```", "", "```"), 1)            # control

    def test_inline_code_line_is_not_a_fence(self):
        body = ("# M\n```code``` hello\n<!--\n" + "".join(f"l{i}\n" for i in range(150)) + "-->\n"
                + "".join(f"- f{i}\n" for i in range(60)) + "- [Late](late-note.md)\n")
        self.write("MEMORY.md", body)
        self.notes("late-note.md")
        code, out, _ = run("check", self.d)
        self.assertEqual((code, unreachable(out)), (0, 0))

    def test_indented_comment_is_code_not_a_comment(self):
        body = ("# M\n    <!--\n" + "".join(f"    l{i}\n" for i in range(150)) + "    -->\n"
                + "".join(f"- f{i}\n" for i in range(60)) + "- [Late](late-note.md)\n")
        self.write("MEMORY.md", body)
        self.notes("late-note.md")
        self.assertEqual(unreachable(run("check", self.d)[1]), 1)

    def test_angle_bracket_filename_round_trips(self):
        self.write("MEMORY.md", "# M\n")
        self.write("a>b.md", fm('description: "odd"'))
        self.write("c<d\\e.md", fm('description: "odder"'))
        run("archive", self.d, "--apply")
        code, out, _ = run("check", self.d)
        self.assertEqual((code, unreachable(out)), (0, 0))

    def test_slug_at_sentence_end_and_wikilink_alias_count(self):
        self.write("MEMORY.md", "# M\n\nSee deploy-checklist. Also [[todo|My todo]] and [[plan#goals]].\n")
        self.notes("deploy-checklist.md", "todo.md", "plan.md")
        code, out, _ = run("check", self.d)
        self.assertEqual((code, unreachable(out)), (0, 0))


class Round4Tests(Base):
    """Final-review findings: --force replaced a foreign archive's directory entry."""

    def test_force_writes_through_a_foreign_archive_symlink(self):
        self.write("MEMORY.md", "# M\n\n- [A](a-note.md)\n")
        self.notes("a-note.md", "b-note.md")
        real_dir = self.d / "elsewhere"
        real_dir.mkdir()
        real = real_dir / "hand-archive.md"
        real.write_text("- [b](b-note.md) - HAND CURATED\n")
        os.chmod(real, 0o600)
        os.symlink(real, self.d / "memory-archive-index.md")
        code, _, err = run("archive", self.d, "--apply", "--force")
        self.assertEqual(code, 0, err)
        self.assertTrue((self.d / "memory-archive-index.md").is_symlink())
        self.assertIn(b"(b-note.md)", real.read_bytes())
        self.assertNotIn(b"HAND CURATED", real.read_bytes())
        self.assertEqual(real.stat().st_mode & 0o777, 0o600)
        backups = [self.d / n for n in self.backups("memory-archive-index.md")]
        self.assertEqual(len(backups), 1)
        self.assertIn(b"HAND CURATED", backups[0].read_bytes())

    def test_force_keeps_a_foreign_archive_mode(self):
        self.write("MEMORY.md", "# M\n\n- [A](a-note.md)\n")
        self.notes("a-note.md", "b-note.md")
        foreign = self.write("memory-archive-index.md", "- [b](b-note.md) - HAND CURATED\n")
        os.chmod(foreign, 0o600)
        code, _, err = run("archive", self.d, "--apply", "--force")
        self.assertEqual(code, 0, err)
        self.assertIn(b"(b-note.md)", foreign.read_bytes())
        self.assertEqual(foreign.stat().st_mode & 0o777, 0o600)

    def test_dangling_archive_symlink_is_refused(self):
        self.write("MEMORY.md", "# M\n\n- [A](a-note.md)\n")
        self.notes("a-note.md", "b-note.md")
        os.symlink(self.d / "missing-archive.md", self.d / "memory-archive-index.md")
        for flags in ((), ("--force",)):
            code, _, err = run("archive", self.d, "--apply", *flags)
            self.assertEqual(code, 2, err)
            self.assertNotIn("Traceback", err)
            self.assertTrue((self.d / "memory-archive-index.md").is_symlink())
            self.assertFalse((self.d / "missing-archive.md").exists())
            self.assertNotIn(b"Archive tier", (self.d / "MEMORY.md").read_bytes())


class Round5Tests(Base):
    """Code-review findings: exit codes, archive aliases, the second recheck, --all, temp files."""

    def basic(self):
        self.write("MEMORY.md", "# M\n\n- [A](a-note.md)\n")
        self.notes("a-note.md", "b-note.md")

    def test_unreadable_folders_exit_2(self):
        code, _, err = run("check", self.d / "no-such-folder")
        self.assertEqual(code, 2)
        self.assertIn("no MEMORY.md", err)
        code, _, err = run("archive", self.d, "--apply")
        self.assertEqual(code, 2)
        self.assertNotIn("Traceback", err)

    def test_unreadable_index_exits_2(self):
        if os.geteuid() == 0:
            self.skipTest("root ignores permissions")
        self.basic()
        os.chmod(self.d / "MEMORY.md", 0)
        try:
            code, _, err = run("check", self.d)
        finally:
            os.chmod(self.d / "MEMORY.md", 0o644)
        self.assertEqual(code, 2)
        self.assertIn("can't read it", err)
        self.assertNotIn("Traceback", err)

    def projects(self):
        home = self.d / "home"
        good = home / ".claude/projects/good/memory"
        good.mkdir(parents=True)
        (good / "MEMORY.md").write_text("# M\n")
        (good / "lost-note.md").write_text(fm('description: "x"'))
        bare = home / ".claude/projects/bare/memory"
        bare.mkdir(parents=True)
        (bare / "stray-note.md").write_text(fm('description: "x"'))
        return home, good, bare

    def test_all_checks_every_folder_with_an_index(self):
        home, good, bare = self.projects()
        code, out, err = run("check", "--all", env=dict(os.environ, HOME=str(home)))
        self.assertEqual(code, 1, err)
        self.assertIn(str(good), out)
        self.assertNotIn(str(bare), out)
        self.assertEqual(unreachable(out), 1)

    def test_all_keeps_going_past_an_unreadable_index(self):
        if os.geteuid() == 0:
            self.skipTest("root ignores permissions")
        home, good, _ = self.projects()
        locked = home / ".claude/projects/locked/memory"
        locked.mkdir(parents=True)
        (locked / "MEMORY.md").write_text("# M\n")
        os.chmod(locked / "MEMORY.md", 0)
        try:
            code, out, err = run("check", "--all", env=dict(os.environ, HOME=str(home)))
        finally:
            os.chmod(locked / "MEMORY.md", 0o644)
        self.assertEqual(code, 2)
        self.assertIn(str(good), out)
        self.assertIn("can't read it", err)
        self.assertNotIn("Traceback", err)

    def test_archive_that_is_the_index_is_refused(self):
        self.basic()
        before = (self.d / "MEMORY.md").read_bytes()
        os.symlink(self.d / "MEMORY.md", self.d / "memory-archive-index.md")
        for flags in ((), ("--force",)):
            code, _, err = run("archive", self.d, "--apply", *flags)
            self.assertEqual(code, 2, err)
            self.assertIn("another name for MEMORY.md", err)
            self.assertEqual((self.d / "MEMORY.md").read_bytes(), before)
            self.assertEqual(self.backups("MEMORY.md"), [])

    def test_archive_hard_linked_to_a_note_is_refused(self):
        self.basic()
        before = (self.d / "b-note.md").read_bytes()
        os.link(self.d / "b-note.md", self.d / "memory-archive-index.md")
        code, _, err = run("archive", self.d, "--apply", "--force")
        self.assertEqual(code, 2, err)
        self.assertIn("another name for b-note.md", err)
        self.assertEqual((self.d / "b-note.md").read_bytes(), before)
        self.assertNotIn(b"Archive tier", (self.d / "MEMORY.md").read_bytes())

    def test_index_edit_after_the_archive_write_is_kept(self):
        mr = load()
        self.basic()
        real = mr.write_new

        def racing(path, data):
            real(path, data)
            with open(self.d / "MEMORY.md", "ab") as f:
                f.write(b"- [Late](late-note.md) added by a live session\n")

        mr.write_new = racing
        code = mr.cmd_archive(self.d, True, False)
        self.assertEqual(code, 2)
        index = (self.d / "MEMORY.md").read_bytes()
        self.assertIn(b"added by a live session", index)
        self.assertNotIn(b"Archive tier", index)
        self.assertIn(b"(b-note.md)", (self.d / "memory-archive-index.md").read_bytes())

    def test_failed_write_leaves_no_temp_file(self):
        from unittest import mock
        mr = load()
        self.basic()
        before = (self.d / "MEMORY.md").read_bytes()
        real_fdopen = os.fdopen

        class Full:
            def __init__(self, f):
                self.f = f

            def __enter__(self):
                return self

            def __exit__(self, *exc):
                self.f.close()

            def write(self, data):
                self.f.write(data[:10])
                raise OSError(28, "No space left on device")

        with mock.patch.object(mr.os, "fdopen", lambda fd, mode: Full(real_fdopen(fd, mode))):
            code = mr.cmd_archive(self.d, True, False)
        self.assertEqual(code, 2)
        self.assertEqual([p.name for p in self.d.iterdir() if ".tmp-" in p.name], [])
        self.assertEqual((self.d / "MEMORY.md").read_bytes(), before)
        self.assertFalse((self.d / "memory-archive-index.md").exists())


class Round6Tests(Base):
    """Final-review findings: a failed in-place write, and notes that can't be listed."""

    def linked(self):
        self.write("MEMORY.md", "# M\n\n- [A](a-note.md)\n")
        os.link(self.d / "MEMORY.md", self.d / "other-link")
        self.notes("a-note.md", "b-note.md")
        return (self.d / "MEMORY.md").read_bytes()

    def failing_writes(self, mr, times):
        """Make the in-place writer's first `times` writes put half their bytes down, then fail."""
        from unittest import mock
        real_open = open
        left = [times]

        class Partial:
            def __init__(self, f):
                self.f = f

            def __enter__(self):
                return self

            def __exit__(self, *exc):
                self.f.close()

            def __getattr__(self, name):
                return getattr(self.f, name)

            def write(self, data):
                if not left[0]:
                    return self.f.write(data)
                left[0] -= 1
                self.f.write(bytes(data[:len(data) // 2]))
                self.f.flush()
                raise OSError(28, "No space left on device")

        def fake_open(file, mode="r", *args, **kwargs):
            f = real_open(file, mode, *args, **kwargs)
            return Partial(f) if mode == "r+b" else f

        return mock.patch.object(mr, "open", fake_open, create=True)

    def test_failed_in_place_write_puts_the_index_back(self):
        mr = load()
        before = self.linked()
        with self.failing_writes(mr, 1):
            code = mr.cmd_archive(self.d, True, False)
        self.assertEqual(code, 2)
        self.assertEqual((self.d / "MEMORY.md").read_bytes(), before)
        self.assertTrue(os.path.samefile(self.d / "MEMORY.md", self.d / "other-link"))

    def test_failed_put_back_is_reported_with_the_backup(self):
        from contextlib import redirect_stderr
        from io import StringIO
        mr = load()
        before = self.linked()
        err = StringIO()
        with self.failing_writes(mr, 2), redirect_stderr(err):
            code = mr.cmd_archive(self.d, True, False)
        self.assertEqual(code, 2)
        self.assertIn("MEMORY.md may be partly written", err.getvalue())
        self.assertNotIn("is unchanged", err.getvalue())
        [backup] = self.backups("MEMORY.md")
        self.assertIn(backup, err.getvalue())
        self.assertEqual((self.d / backup).read_bytes(), before)

    def test_unlistable_note_alone_is_not_reported_as_done(self):
        self.write("MEMORY.md", "# M\n\n- [A](a-note.md)\n")
        self.notes("a-note.md", "bad\nname.md")
        for flags in ((), ("--apply",)):
            code, out, err = run("archive", self.d, *flags)
            self.assertEqual(code, 2, out + err)
            self.assertNotIn("nothing to archive", out)
            self.assertIn("line break", err)
        self.assertFalse((self.d / "memory-archive-index.md").exists())
        self.assertEqual(self.backups("MEMORY.md"), [])

    def test_unlistable_note_stops_the_run_before_writing(self):
        self.write("MEMORY.md", "# M\n\n- [A](a-note.md)\n")
        self.notes("a-note.md", "b-note.md", "bad\rname.md")
        before = (self.d / "MEMORY.md").read_bytes()
        code, _, err = run("archive", self.d, "--apply")
        self.assertEqual(code, 2, err)
        self.assertIn("'bad\\rname.md'", err)
        self.assertIn("nothing changed", err)
        self.assertEqual((self.d / "MEMORY.md").read_bytes(), before)
        self.assertFalse((self.d / "memory-archive-index.md").exists())
        self.assertEqual(self.backups("MEMORY.md"), [])


if __name__ == "__main__":
    unittest.main()
