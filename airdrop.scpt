-- 最新の画像フォルダを探す
set outputDir to "/Users/ikenagahironari/amazon_to_mercari/output/"

tell application "Finder"
    set allFolders to folders of (POSIX file outputDir as alias)
    if (count of allFolders) is 0 then
        display alert "画像フォルダが見つかりません"
        return
    end if
    set latestFolder to item (count of allFolders) of allFolders
    set imagesFolder to folder "images" of latestFolder

    activate
    open imagesFolder
    delay 3
end tell

tell application "System Events"
    tell process "Finder"
        -- ウィンドウ内をクリックしてフォーカス
        set theWindow to window 1
        set thePos to position of theWindow
        set theSize to size of theWindow
        set clickX to (item 1 of thePos) + 100
        set clickY to (item 2 of thePos) + (item 2 of theSize) / 2
        click at {clickX, clickY}
        delay 0.5

        -- Command+A で全選択
        keystroke "a" using command down
        delay 1

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
        delay 2

        -- 共有シートからAirDropをクリック
        if exists button "AirDrop" of window 1 then
            click button "AirDrop" of window 1
        else
            -- シートの中を探す
            if exists sheet 1 of window 1 then
                click button "AirDrop" of sheet 1 of window 1
            end if
        end if
    end tell
end tell
