// JXA (JavaScript for Automation) でAirDropを直接起動
ObjC.import('Foundation');
ObjC.import('AppKit');

// 最新の画像フォルダを取得
var fm = $.NSFileManager.defaultManager;
var outputDir = $.NSString.stringWithString('/Users/ikenagahironari/amazon_to_mercari/output');
var contents = fm.contentsOfDirectoryAtPathError(outputDir, null);

if (contents.count == 0) {
    var app = Application.currentApplication();
    app.includeStandardAdditions = true;
    app.displayAlert('画像フォルダが見つかりません');
} else {
    // 最新フォルダを取得
    var folders = [];
    for (var i = 0; i < contents.count; i++) {
        folders.push(contents.objectAtIndex(i).js);
    }
    folders.sort();
    var latestFolder = folders[folders.length - 1];
    var imagesDir = '/Users/ikenagahironari/amazon_to_mercari/output/' + latestFolder + '/images';

    // 画像ファイルを取得
    var imageContents = fm.contentsOfDirectoryAtPathError(imagesDir, null);
    var fileURLs = [];
    for (var j = 0; j < imageContents.count; j++) {
        var filename = imageContents.objectAtIndex(j).js;
        if (filename.match(/\.(jpg|jpeg|png)$/i)) {
            var filePath = imagesDir + '/' + filename;
            var url = $.NSURL.fileURLWithPath(filePath);
            fileURLs.push(url);
        }
    }

    if (fileURLs.length == 0) {
        var app2 = Application.currentApplication();
        app2.includeStandardAdditions = true;
        app2.displayAlert('画像ファイルが見つかりません');
    } else {
        // AirDrop共有サービスを直接起動
        var nsArray = $.NSArray.arrayWithArray(fileURLs);
        var service = $.NSSharingService.sharingServiceNamed('com.apple.share.AirDrop.send');
        if (service.canPerformWithItems(nsArray)) {
            service.performWithItems(nsArray);
        } else {
            var app3 = Application.currentApplication();
            app3.includeStandardAdditions = true;
            app3.displayAlert('AirDropが使用できません。BluetoothとWi-Fiを確認してください。');
        }
    }
}
