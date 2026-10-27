// Vito: the render with a masked layer per enhanced crop -> result.psd + result.jpg.
// Run by tools/assemble.py through Photoshop's COM (DoJavaScriptFile) with one argument: the path
// of the manifest it writes. Crops come in paste order (far first), each:
//   {id, name, file, box: [x0, y0, x1, y1], feather}
// Per crop: open the enhanced PNG, scale it to its box, copy it into the render as a layer at
// the box inside the group `job.group` (the later crop on top), Select Subject on that layer
// alone, the selection becomes the layer mask. A crop where
// Select Subject finds nothing stays as a hidden layer without a mask and is reported.
// Writes the manifest's `report` file: one line per crop, "<id>\tmasked|no subject|error: ...".

function readText(path) {
    var f = new File(path);
    f.encoding = "UTF-8";
    f.open("r");
    var s = f.read();
    f.close();
    return s;
}

function writeText(path, text) {
    var f = new File(path);
    f.encoding = "UTF-8";
    f.open("w");
    f.write(text);
    f.close();
}

function selectSubject() {
    var d = new ActionDescriptor();
    d.putBoolean(stringIDToTypeID("sampleAllLayers"), false);
    executeAction(stringIDToTypeID("autoCutout"), d, DialogModes.NO);
}

function hasSelection(doc) {
    try {
        doc.selection.bounds;
        return true;
    } catch (e) {
        return false;
    }
}

function maskFromSelection() {
    var d = new ActionDescriptor();
    d.putClass(charIDToTypeID("Nw  "), charIDToTypeID("Chnl"));
    var r = new ActionReference();
    r.putEnumerated(charIDToTypeID("Chnl"), charIDToTypeID("Chnl"), charIDToTypeID("Msk "));
    d.putReference(charIDToTypeID("At  "), r);
    d.putEnumerated(charIDToTypeID("Usng"), charIDToTypeID("UsrM"), charIDToTypeID("RvlS"));
    executeAction(charIDToTypeID("Mk  "), d, DialogModes.NO);
}

function pasteCrop(doc, c) {
    var w = c.box[2] - c.box[0], h = c.box[3] - c.box[1];
    var src = app.open(new File(c.file));
    if (src.mode != DocumentMode.RGB) src.changeMode(ChangeMode.RGB);
    if (src.bitsPerChannel != doc.bitsPerChannel) src.bitsPerChannel = doc.bitsPerChannel;
    if (src.layers.length > 1) src.flatten();
    src.resizeImage(UnitValue(w, "px"), UnitValue(h, "px"), undefined, ResampleMethod.BICUBIC);
    var layer = src.activeLayer.duplicate(doc, ElementPlacement.PLACEATBEGINNING);
    src.close(SaveOptions.DONOTSAVECHANGES);
    app.activeDocument = doc;
    doc.activeLayer = layer;
    layer.name = c.name;
    var b = layer.bounds;
    layer.translate(c.box[0] - b[0].as("px"), c.box[1] - b[1].as("px"));
    return layer;
}

function main(manifestPath) {
    var job = eval("(" + readText(manifestPath) + ")");
    var units = app.preferences.rulerUnits;
    var dialogs = app.displayDialogs;
    app.preferences.rulerUnits = Units.PIXELS;
    app.displayDialogs = DialogModes.NO;
    var report = [];
    try {
        var doc = app.open(new File(job.render));
        var group = doc.layerSets.add();
        group.name = job.group;
        for (var i = 0; i < job.crops.length; i++) {
            var c = job.crops[i];
            try {
                var layer = pasteCrop(doc, c);
                layer.move(group, ElementPlacement.PLACEATBEGINNING);
                doc.activeLayer = layer;
                doc.selection.deselect();
                selectSubject();
                if (!hasSelection(doc)) {
                    layer.visible = false;
                    report.push(c.id + "\tno subject");
                    continue;
                }
                if (c.feather > 0) doc.selection.feather(c.feather);
                maskFromSelection();
                doc.selection.deselect();
                report.push(c.id + "\tmasked");
            } catch (e) {
                report.push(c.id + "\terror: " + e);
            }
        }
        doc.saveAs(new File(job.psd), new PhotoshopSaveOptions(), true);
        var jpg = new JPEGSaveOptions();
        jpg.quality = 11;
        doc.saveAs(new File(job.jpg), jpg, true);
        doc.close(SaveOptions.DONOTSAVECHANGES);
    } catch (e) {
        report.push("*\terror: " + e);
    } finally {
        app.preferences.rulerUnits = units;
        app.displayDialogs = dialogs;
        writeText(job.report, report.join("\n"));
    }
    return report.join("\n");
}

main(arguments[0]);
