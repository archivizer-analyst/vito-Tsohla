// Vito: the render with a masked layer per enhanced crop -> result.psd + result.jpg.
// Run by tools/assemble.py through Photoshop's COM (DoJavaScriptFile) with one argument: the path
// of the manifest it writes. Crops come in paste order (far first), each:
//   {id, name, file, box: [x0, y0, x1, y1], feather}
// Per crop: open the enhanced image, make it a smart object at its own resolution, copy it into
// the render inside the group `job.group` (the later crop on top) and scale it onto its box. The
// smart object keeps every pixel the generator made: stretching it along one side to fix the
// proportions, or upscaling the render later, does not lose resolution. A crop where Select
// Subject finds nothing stays as a hidden layer without a mask and is reported.
// Select Subject runs on the enhanced image alone, in its own document and at its own resolution,
// before it becomes a smart object; the mask goes with the layer and scales with it. A mask that
// covers more than `job.max_cover` of its crop has taken the crop, not its people (Photoshop 27.x
// on the server did that to almost every crop): the layer stays hidden with that mask.
// Writes the manifest's `report` file: "*\tphotoshop <version>", then one line per crop,
// "<id>\tmasked\t<cover>%" | "<id>\tbad mask\t<cover>%" | "<id>\tno subject" | "<id>\terror: ...".

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

// Share of the selection in the document: the mean of the alpha channel it is stored in. A grayscale
// copy of it is averaged (Blur > Average) and its one value read (histograms of the mask itself
// came out too low).
function selectChannel(ref) {
    var d = new ActionDescriptor();
    d.putReference(charIDToTypeID("null"), ref);
    executeAction(charIDToTypeID("slct"), d, DialogModes.NO);
}

function coverage(d, ch) {
    var r = new ActionReference();
    r.putName(charIDToTypeID("Chnl"), ch.name);
    selectChannel(r);                           // the copy takes the target channel
    d.selection.selectAll();
    d.selection.copy();
    d.selection.deselect();
    r = new ActionReference();
    r.putEnumerated(charIDToTypeID("Chnl"), charIDToTypeID("Chnl"), charIDToTypeID("RGB "));
    selectChannel(r);
    var g = app.documents.add(d.width, d.height, d.resolution, "vito_cover", NewDocumentMode.GRAYSCALE);
    g.paste();
    g.flatten();
    g.activeLayer.applyAverage();
    var hist = g.channels[0].histogram, best = 0;
    g.close(SaveOptions.DONOTSAVECHANGES);
    app.activeDocument = d;
    for (var v = 1; v < 256; v++)
        if (hist[v] > hist[best]) best = v;
    return best / 255;
}

// The enhanced image becomes a smart object with its mask, in its own document: Select Subject sees
// only this image at its full resolution, whatever layers and settings the render has. Returns
// {layer, cover}: cover is the masked share of the crop, -1 when Select Subject found nothing.
function pasteCrop(doc, c) {
    var w = c.box[2] - c.box[0], h = c.box[3] - c.box[1];
    var src = app.open(new File(c.file));
    if (src.mode != DocumentMode.RGB) src.changeMode(ChangeMode.RGB);
    if (src.bitsPerChannel != doc.bitsPerChannel) src.bitsPerChannel = doc.bitsPerChannel;
    if (src.layers.length > 1) src.flatten();
    if (src.resolution != doc.resolution)      // same ppi: the copy keeps its pixel size
        src.resizeImage(undefined, undefined, doc.resolution, ResampleMethod.NONE);
    src.selection.deselect();
    selectSubject();
    var ch = null, cover = -1;
    if (hasSelection(src)) {
        var f = c.feather * src.width.as("px") / w;     // feather is in render px
        if (f > 0) src.selection.feather(f);
        ch = src.channels.add();
        src.selection.store(ch);
        cover = coverage(src, ch);
        src.selection.deselect();
    }
    executeAction(stringIDToTypeID("newPlacedLayer"), undefined, DialogModes.NO);
    if (ch) {
        src.selection.load(ch);
        maskFromSelection();
        src.selection.deselect();
    }
    var layer = src.activeLayer.duplicate(doc, ElementPlacement.PLACEATBEGINNING);
    src.close(SaveOptions.DONOTSAVECHANGES);
    app.activeDocument = doc;
    doc.activeLayer = layer;
    layer.name = c.name;
    var b = layer.bounds;
    var bw = b[2].as("px") - b[0].as("px"), bh = b[3].as("px") - b[1].as("px");
    layer.resize(100 * w / bw, 100 * h / bh, AnchorPosition.TOPLEFT);   // the linked mask follows
    b = layer.bounds;
    layer.translate(c.box[0] - b[0].as("px"), c.box[1] - b[1].as("px"));
    return {layer: layer, cover: cover};
}

function main(manifestPath) {
    var job = eval("(" + readText(manifestPath) + ")");
    var units = app.preferences.rulerUnits;
    var dialogs = app.displayDialogs;
    app.preferences.rulerUnits = Units.PIXELS;
    app.displayDialogs = DialogModes.NO;
    var report = ["*\tphotoshop " + app.version];
    try {
        var doc = app.open(new File(job.render));
        var group = doc.layerSets.add();
        group.name = job.group;
        for (var i = 0; i < job.crops.length; i++) {
            var c = job.crops[i];
            try {
                var r = pasteCrop(doc, c);
                r.layer.move(group, ElementPlacement.PLACEATBEGINNING);
                var pct = Math.round(100 * r.cover) + "%";
                if (r.cover < 0) {
                    r.layer.visible = false;
                    report.push(c.id + "\tno subject");
                } else if (r.cover > job.max_cover) {   // the whole crop, not its people
                    r.layer.visible = false;
                    report.push(c.id + "\tbad mask\t" + pct);
                } else {
                    report.push(c.id + "\tmasked\t" + pct);
                }
            } catch (e) {
                report.push(c.id + "\terror: " + e);
            }
        }
        doc.saveAs(new File(job.psd), new PhotoshopSaveOptions(), true);
        var jpg = new JPEGSaveOptions();
        jpg.quality = 11;
        doc.saveAs(new File(job.jpg), jpg, true);
        doc.close(SaveOptions.DONOTSAVECHANGES);
        app.purge(PurgeTarget.ALLCACHES);       // Photoshop stays open between assemblies
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
