// Vito: the render with a masked layer per enhanced crop -> result.psd + result.jpg.
// Run by tools/assemble.py through Photoshop's COM (DoJavaScriptFile) with one argument: the path
// of the manifest it writes. Crops come in paste order (far first), each:
//   {id, name, file, box: [x0, y0, x1, y1], people_box: [x0, y0, x1, y1], feather}
// Per crop: open the enhanced image, make it a smart object at its own resolution, copy it into
// the render inside the group `job.group` (the later crop on top) and scale it onto its box. The
// smart object keeps every pixel the generator made: stretching it along one side to fix the
// proportions, or upscaling the render later, does not lose resolution. A crop where nothing is
// selected stays as a hidden layer without a mask and is reported.
// The mask: Select People (Photoshop 27+), only the crop's own people, those at least
// `job.own_person` inside its people box; the people of the next crops that stand in its context
// are left to their own layers, and furniture is not taken. Without Select People, or when it finds
// none of the crop's own, Select Subject (it takes the foreground: chairs and tables with the
// people). Either runs on the enhanced image alone, in its own document and at its own resolution,
// before it becomes a smart object; the mask goes with the layer and scales with it. A mask that
// covers more than `job.max_cover` of its crop has taken the crop, not its people: the layer stays
// hidden with that mask. (Photoshop 27.x does that to almost every crop when Select Subject runs on
// the crop's layer inside the render, as the first version did; in the crop's own document it does
// not.)
// Writes the manifest's `report` file: "*\tphotoshop <version>", then one line per crop,
// "<id>\tmasked\t<cover>%\t<how>" | "<id>\tbad mask\t<cover>%\t<how>" | "<id>\tno subject" |
// "<id>\terror: ...", <how> being "people <N>" or "subject".

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

// Select People: the people Photoshop finds in the document, one at a time (numbered from 1), kept
// when at least `own` of a person's bounds lie in `pb` (the crop's own people box, document px);
// then selects the kept ones together. Returns how many were kept, -1 without Select People
// (Photoshop before 27).
function selectOwnPeople(doc, pb, own) {
    var keep = new ActionList(), n = 0;
    for (var i = 1; i <= 100; i++) {
        doc.selection.deselect();
        var d = new ActionDescriptor(), l = new ActionList();
        l.putInteger(i);
        d.putList(stringIDToTypeID("people"), l);
        try {
            executeAction(stringIDToTypeID("selectPeople"), d, DialogModes.NO);
        } catch (e) {
            if (i == 1) return -1;
            break;
        }
        if (!hasSelection(doc)) break;
        var b = doc.selection.bounds;
        var x0 = b[0].as("px"), y0 = b[1].as("px"), x1 = b[2].as("px"), y1 = b[3].as("px");
        var ix = Math.max(0, Math.min(x1, pb[2]) - Math.max(x0, pb[0]));
        var iy = Math.max(0, Math.min(y1, pb[3]) - Math.max(y0, pb[1]));
        if (ix * iy >= own * (x1 - x0) * (y1 - y0)) {
            keep.putInteger(i);
            n++;
        }
    }
    doc.selection.deselect();
    if (n) {
        var s = new ActionDescriptor();
        s.putList(stringIDToTypeID("people"), keep);
        executeAction(stringIDToTypeID("selectPeople"), s, DialogModes.NO);
    }
    return n;
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

// Top-left corner [x, y] of the active smart object's content in document px, mask or not.
function corners() {
    var r = new ActionReference();
    r.putEnumerated(charIDToTypeID("Lyr "), charIDToTypeID("Ordn"), charIDToTypeID("Trgt"));
    var t = executeActionGet(r).getObjectValue(stringIDToTypeID("smartObjectMore"))
        .getList(stringIDToTypeID("transform"));
    return [Math.min(t.getDouble(0), t.getDouble(6)), Math.min(t.getDouble(1), t.getDouble(3))];
}

// The enhanced image becomes a smart object with its mask, in its own document: the selection sees
// only this image at its full resolution, whatever layers and settings the render has. Returns
// {layer, cover, how}: cover is the masked share of the crop, -1 when nothing was selected; how is
// "people N" (Select People kept N of the crop's own people) or "subject" (Select Subject).
function pasteCrop(doc, c, own) {
    var w = c.box[2] - c.box[0], h = c.box[3] - c.box[1];
    var src = app.open(new File(c.file));
    if (src.mode != DocumentMode.RGB) src.changeMode(ChangeMode.RGB);
    if (src.bitsPerChannel != doc.bitsPerChannel) src.bitsPerChannel = doc.bitsPerChannel;
    if (src.layers.length > 1) src.flatten();
    if (src.resolution != doc.resolution)      // same ppi: the copy keeps its pixel size
        src.resizeImage(undefined, undefined, doc.resolution, ResampleMethod.NONE);
    var srcW = src.width.as("px"), srcH = src.height.as("px");
    var sx = srcW / w, sy = srcH / h, pb = c.people_box;
    var n = selectOwnPeople(src, [(pb[0] - c.box[0]) * sx, (pb[1] - c.box[1]) * sy,
                                  (pb[2] - c.box[0]) * sx, (pb[3] - c.box[1]) * sy], own);
    var how = "people " + n;
    if (n <= 0) {                                   // no Select People, or none of the crop's own
        src.selection.deselect();
        selectSubject();
        how = "subject";
    }
    var ch = null, cover = -1;
    if (hasSelection(src)) {
        var f = c.feather * srcW / w;                   // feather is in render px
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
    // Not from layer.bounds: a masked layer's bounds are its mask's, not the crop's. The scale comes
    // from the crop's own pixel size, the offset from the smart object's corners.
    layer.resize(100 * w / srcW, 100 * h / srcH, AnchorPosition.TOPLEFT);   // the linked mask follows
    var q = corners();
    layer.translate(c.box[0] - q[0], c.box[1] - q[1]);
    return {layer: layer, cover: cover, how: how};
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
                var r = pasteCrop(doc, c, job.own_person);
                r.layer.move(group, ElementPlacement.PLACEATBEGINNING);
                var pct = Math.round(100 * r.cover) + "%";
                if (r.cover < 0) {
                    r.layer.visible = false;
                    report.push(c.id + "\tno subject");
                } else if (r.cover > job.max_cover) {   // the whole crop, not its people
                    r.layer.visible = false;
                    report.push(c.id + "\tbad mask\t" + pct + "\t" + r.how);
                } else {
                    report.push(c.id + "\tmasked\t" + pct + "\t" + r.how);
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
