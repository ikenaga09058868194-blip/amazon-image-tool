-- 共有シートを開いてUI要素を調べる
tell application "Finder"
    activate
end tell

delay 1

tell application "System Events"
    tell process "Finder"
        -- ファイルメニューから「共有…」をクリック
        tell menu bar 1
            tell menu bar item "ファイル"
                click
                delay 0.8
                tell menu "ファイル"
                    click menu item "共有…"
                end tell
            end tell
        end tell
        delay 3

        -- 全ウィンドウとシートのボタン名を取得
        set output to ""
        repeat with w in windows
            set output to output & "Window: " & name of w & return
            try
                repeat with b in buttons of w
                    set output to output & "  Button: " & description of b & return
                end repeat
            end try
            try
                repeat with s in sheets of w
                    set output to output & "  Sheet found" & return
                    repeat with b in buttons of s
                        set output to output & "    Sheet Button: " & description of b & return
                    end repeat
                end repeat
            end try
        end repeat

        do shell script "echo " & quoted form of output & " > /tmp/share_debug.txt"
    end tell
end tell
