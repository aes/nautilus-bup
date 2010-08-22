import sys, stat, time, os.path, gtk, urllib, gnomevfs, nautilus

sys.path.append('/usr/lib/bup')
from bup import options, git, vfs, helpers

git.check_repo_or_die()

def hexhash(fo): return ''.join(["%02x"%ord(c) for c in fo.hash])

def pump(src, tgt, prg=lambda i,n: i):
    for blob in helpers.chunkyreader(src):
        tgt.write(blob); prg(len(blob))
    src.close(); tgt.close()

def find_versions(pn, abbrev=True):
    l = []
    for s in vfs.RefList(None).subs():
        for v in s.subs():
            if stat.S_ISLNK(v.mode): continue
            try:
                fu = v.try_resolve(pn[1:])
                if fu: l.append((v.mtime, v, fu))
            except: pass
    l.sort()
    if not abbrev: return l
    m = []
    h = None
    for tdf in l:
        if h != tdf[-1].hash:
            h = tdf[-1].hash
            m.append(tdf)
    return m

class BupPropertyPage(nautilus.PropertyPageProvider):
    labeltext = '<span size="x-large" weight="bold">Bup history</span>'
    fcd = {"title":   "Restore to...",
           "action":   gtk.FILE_CHOOSER_ACTION_SAVE,
           "buttons": (gtk.STOCK_CANCEL, gtk.RESPONSE_CANCEL,
                       gtk.STOCK_SAVE,   gtk.RESPONSE_ACCEPT)}
    progress_limit = 2**63 # ginormous, we don't want this to happen yet.
    #
    def get_property_pages(self, ff):
        if len(ff) != 1 or ff[0].get_uri_scheme() != 'file': return
        pn = urllib.unquote(ff[0].get_uri()[7:])
        tdf = find_versions(pn)
        if not tdf: return
        #
        return nautilus.PropertyPage("NautilusPython::bup",
                                     gtk.Label('Backup'),
                                     self.build_widget(pn, tdf)),
    def build_treelist(self, pn, tdf):
        ls   = gtk.ListStore(str, str, str, object, object)
        mt = os.stat(pn).st_mtime
        for t,d,f in tdf:
            rem = ["", " (current)"][t > mt]
            ls.append([time.ctime(t)+rem, str(f.size()), hexhash(f), d, f])
        #
        tv   = gtk.TreeView(ls)
        for i,n in enumerate(["Time","Size","Hash"]):
            col = gtk.TreeViewColumn(n, gtk.CellRendererText(), text=i)
            col.set_resizable(True)
            col.set_reorderable(True)
            tv.append_column(col)
        #
        scw  = gtk.ScrolledWindow()
        scw.set_policy(gtk.POLICY_AUTOMATIC, gtk.POLICY_AUTOMATIC)
        scw.add(tv)
        return scw, tv
    def on_save_as(self, widget, tv):
        ts = tv.get_selection()
        ls, it = ts.get_selected()
        if not it: return
        fo = ls.get(it, 4)
        if not fo: return
        self.run_dialog(fo[0])
    def run_dialog(self, fo):
        path = fo.fullname()[len(fo.fs_top().fullname()):]
        i = path.rindex('/')
        dirname, filename = path[:i], path[i+1:]
        fc = gtk.FileChooserDialog(**self.fcd)
        fc.set_do_overwrite_confirmation(True)
        fc.set_current_folder(dirname)
        fc.set_name(filename)
        try:
            if fc.run() == gtk.RESPONSE_ACCEPT:
                if fo.size > self.progress_limit:
                    pass # fixme: make progress dlg
                pump(fo.open(), file(fc.get_filename(), 'w'), fo.size)
        finally:
            fc.destroy()
        #
    def build_widget(self, pn, tdf):
        lbl = gtk.Label(self.labeltext)
        lbl.set_use_markup(True)
        scw, tv = self.build_treelist(pn, tdf)
        btn = gtk.Button(stock='gtk-save-as')
        btn.connect("clicked", self.on_save_as, tv)
        vbox = gtk.VBox(False, 0)
        vbox.add(lbl); vbox.set_child_packing(lbl, 0,0,4, gtk.PACK_START)
        vbox.add(scw); vbox.set_child_packing(scw, 1,1,0, gtk.PACK_START)
        vbox.add(btn); vbox.set_child_packing(btn, 0,0,4, gtk.PACK_END)
        vbox.show_all()
        return vbox
