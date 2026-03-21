-- 共有シートを開く
tell application "Finder"
    activate
end tell
delay 1

tell application "System Events"
    tell process "Finder"
        tell menu bar 1
            tell menu bar item "ファイル"
                click
                delay 0.8
                tell menu "ファイル"
                    click menu item "共有…"
                end tell
            end tell
        end tell
    end tell
end tell

delay 3

-- 全プロセスからAirDropボタンを探す
tell application "System Events"
    set output to ""
    repeat with proc in processes whose background only is false
        try
            set pName to name of proc
            repeat with w in windows of proc
                try
                    set wName to name of w
                    set output to output & pName & " > " & wName & return
                    repeat with b in buttons of w
                        try
                            set output to output & "  btn: " & description of b & return
                        end try
                    end repeat
                end try
            end repeat
        end try
    end repeat
    do shell script "echo " & quoted form of output & " > /tmp/share_debug2.txt"
end tell
