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

delay 2

-- 全プロセスを深くスキャン
tell application "System Events"
    set output to ""
    repeat with proc in processes whose background only is false
        try
            set pName to name of proc
            -- ウィンドウタイプ以外も含めて全UI要素を取得
            set allUI to UI elements of proc
            repeat with el in allUI
                try
                    set elRole to role of el
                    set elTitle to ""
                    try
                        set elTitle to title of el
                    end try
                    set elDesc to ""
                    try
                        set elDesc to description of el
                    end try
                    if elTitle contains "AirDrop" or elDesc contains "AirDrop" or elTitle contains "Air" then
                        set output to output & "★ 発見! " & pName & " | " & elRole & " | " & elTitle & " | " & elDesc & return
                    end if
                    -- 全要素も記録
                    set output to output & pName & " | " & elRole & " | " & elTitle & return
                end try
            end repeat
        end try
    end repeat
    do shell script "echo " & quoted form of output & " > /tmp/share_debug3.txt"
end tell
