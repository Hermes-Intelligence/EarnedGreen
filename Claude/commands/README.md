# Claude command content (staging home)

Files here are promoted slash-command CONTENT, not live commands. The promotion
tool (`tools/promote-candidate.ps1`) deliberately forbids `.claude/commands/` as
a target, so promoted command definitions land in this directory instead.

To activate one as a real slash command, the owner copies it manually, e.g.:

```powershell
Copy-Item Claude/commands/weekly-hygiene.md .claude/commands/weekly-hygiene.md
```

That copy is a human decision recorded in the working tree; nothing in this
repository performs it automatically. Rolling back a release removes the file
here but never touches `.claude/commands/`, so a manually activated command
must also be removed manually.
