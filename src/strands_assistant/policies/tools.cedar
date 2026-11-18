// Hard limits on tool calls. These run before the approval prompt, and a forbid always wins.
//
// context.session.command is the terminal_exec command, lower-cased with runs of spaces collapsed
// (empty for other tools), so "Remove-Item  -Recurse" and "remove-item -recurse" match the same rule.
// Matching command text can be bypassed (aliases, scripts, encoded commands), so this is one layer
// of defence, not containment. Real containment needs the Docker shell option.

// Everything not forbidden below goes on to the approval gate.
@id("default-permit")
permit(principal, action, resource);

// Cloud mode builds the agent without a shell. This catches it being added back by mistake.
@id("no-shell-in-cloud")
forbid(principal, action == Action::"terminal_exec", resource)
when { context.session.cloud_mode };

@id("no-recursive-delete")
forbid(principal, action == Action::"terminal_exec", resource)
when {
  context.session.command like "*rm -rf*" ||
  context.session.command like "*rm -fr*" ||
  context.session.command like "*rm -r *" ||
  (context.session.command like "*remove-item*" && context.session.command like "*-recurse*") ||
  context.session.command like "*rd /s*" ||
  context.session.command like "*rmdir /s*" ||
  context.session.command like "*del /s*" ||
  context.session.command like "*del /q /s*" ||
  context.session.command like "*erase /s*"
};

@id("no-disk-or-system-damage")
forbid(principal, action == Action::"terminal_exec", resource)
when {
  context.session.command like "format *" ||
  context.session.command like "*format-volume*" ||
  context.session.command like "*clear-disk*" ||
  context.session.command like "*diskpart*" ||
  context.session.command like "*mkfs*" ||
  context.session.command like "*dd if=*" ||
  context.session.command like "*cipher /w*" ||
  context.session.command like "*reg delete*" ||
  context.session.command like "*remove-itemproperty*hklm*" ||
  context.session.command like "*bcdedit*" ||
  context.session.command like "*vssadmin delete*"
};

@id("no-shutdown")
forbid(principal, action == Action::"terminal_exec", resource)
when {
  context.session.command like "*shutdown*" ||
  context.session.command like "*stop-computer*" ||
  context.session.command like "*restart-computer*"
};
