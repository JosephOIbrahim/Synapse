# quote-safe.ps1 - central quoting + encoding helpers for the SYNAPSE harness.
#
# Dot-source it (it defines functions, it does not run anything):
#     . (Join-Path $PSScriptRoot 'lib\quote-safe.ps1')          # from harness/
#     . (Join-Path $PSScriptRoot '..\..\lib\quote-safe.ps1')    # from harness/notes/base_control/
#
# It exists to kill two lived failure classes (see harness/HARDENING-SPEC.md):
#
#   S1  unquoted-interpolation - an uncontrolled string (a leg NAME, leg id,
#       branch, path, or prompt) is interpolated into a quoted PowerShell / git
#       / here-string context and shreds it. First lived instance 0522ad0e
#       (2026-06-24); costliest 943e5375 (2026-07-26, a 2000-char brief split at
#       the first quote; two legs ran 2.5h truncated). The point-fix was
#       `$leg.name -replace "'","''"` at orchestrate.ps1:243 - Sanitize-SQ
#       generalizes it so every uncontrolled string gets the same treatment.
#
#   S8  BOM / encoding landmine - PowerShell 5.1 `Set-Content -Encoding utf8`
#       writes a UTF-8 BOM. A BOM on the live Houdini synapse.json made the
#       package fail to load silently (121894d9); a BOM on resolved_lines.json
#       makes json.load raise "Unexpected UTF-8 BOM". Write-Utf8NoBom writes
#       UTF-8 with NO BOM while preserving unicode (an em-dash in a leg name
#       survives; -Encoding ascii would mangle it).
#
# Python twin: harness/autorevise/quote_safe.py (sanitize_sq / ps_single_quote /
# write_json_no_bom) - same contract, used as the test oracle.
#
# This file only DEFINES functions; it never mutates the caller's state (no
# Set-StrictMode, no preference changes), so it is safe to dot-source anywhere.

function Sanitize-SQ {
    <#
    .SYNOPSIS
    Make an arbitrary string safe to embed inside a PowerShell SINGLE-quoted
    literal '...'.

    .DESCRIPTION
    In a single-quoted literal the ONLY metacharacter is the single quote
    itself, which is escaped by doubling it (''). Nothing else - not $, not
    backtick, not double-quote - is special inside '...'. So doubling the
    apostrophe is the complete and correct escape for that context. This is the
    generalization of the safeName point-fix; use it for a leg id, branch,
    path, or any uncontrolled string that lands between single quotes in a
    generated script.

    NOTE: this escapes for a SINGLE-quoted context. It does NOT make a string
    safe for a double-quoted context (where $ and backtick are live) - the
    harness deliberately routes every interpolated value through a single-quoted
    literal in the generated runner, which is what makes this the right tool.

    .EXAMPLE
    $safe = Sanitize-SQ "O'Brien"      # -> O''Brien   (goes inside '...')
    #>
    param([Parameter(Position = 0, ValueFromPipeline = $true)][AllowNull()][AllowEmptyString()]$Value)
    process {
        if ($null -eq $Value) { return '' }
        return ([string]$Value) -replace "'", "''"
    }
}

function Write-Utf8NoBom {
    <#
    .SYNOPSIS
    Write text to a file as UTF-8 with NO byte-order mark, unicode preserved.

    .DESCRIPTION
    Drop-in replacement for `... | Set-Content -Path $p -Encoding utf8`, which
    on Windows PowerShell 5.1 prepends a UTF-8 BOM. Pipeline input is collected
    and joined with the platform newline (matching Set-Content's array
    handling), with a single trailing newline, then written via
    System.IO.File::WriteAllText with a BOM-less UTF8Encoding.

    .EXAMPLE
    ($obj | ConvertTo-Json -Compress) | Write-Utf8NoBom -Path $lock
    @"
    ...runner...
    "@ | Write-Utf8NoBom -Path $script
    #>
    param(
        [Parameter(Mandatory = $true)][string]$Path,
        [Parameter(Mandatory = $true, ValueFromPipeline = $true)][AllowEmptyString()][AllowNull()]$Value
    )
    begin { $lines = New-Object System.Collections.Generic.List[string] }
    process { $lines.Add([string]$Value) }
    end {
        $text = [string]::Join([Environment]::NewLine, $lines) + [Environment]::NewLine
        $enc  = New-Object System.Text.UTF8Encoding($false)   # $false => emit no BOM
        [System.IO.File]::WriteAllText($Path, $text, $enc)
    }
}
