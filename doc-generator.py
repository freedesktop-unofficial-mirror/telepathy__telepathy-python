#!/usr/bin/python2.4
import sys
import os
import inspect
import dbus

inspectmod=__import__(sys.argv[1],[],[],[])

doc={}

for (cname,val) in inspectmod.__dict__.items():
    if inspect.isclass(val):
        if val.__dict__.has_key("_dbus_interfaces"):
            iname=val._dbus_interfaces[val.__name__]
            doc[iname]={}
            doc[iname]["maintext"]=val.__doc__
            doc[iname]["methods"]={}
            doc[iname]["signals"]={}
        for (mname, mval) in val.__dict__.items():
            if inspect.isfunction(mval) and mval.__dict__.has_key("_dbus_is_method"):
                iname=mval.__dict__["_dbus_interface"]
                if not doc.has_key(iname):
                    doc[iname]={}
                    doc[iname]["maintext"]=val.__doc__
                    doc[iname]["methods"]={}
                    doc[iname]["signals"]={}
                doc[iname]["methods"][mname]={}
                sigin=dbus.Signature(mval.__dict__["_dbus_in_signature"])
                argspec=inspect.getargspec(mval)
                args=', '.join(map(lambda tup: str(tup[0])+": "+tup[1], zip(sigin,argspec[0][1:]))) # chop off self
                doc[iname]["methods"][mname]["in_sig"]=args
                if mval.__dict__["_dbus_out_signature"] == "":
                    doc[iname]["methods"][mname]["out_sig"]="None"
                else:
                    doc[iname]["methods"][mname]["out_sig"]=mval.__dict__["_dbus_out_signature"]
                doc[iname]["methods"][mname]["text"]= mval.__doc__
            if inspect.isfunction(mval) and mval.__dict__.has_key("_dbus_is_signal"):
                iname=mval.__dict__["_dbus_interface"]
                if not doc.has_key(iname):
                    doc[iname]={}
                    doc[iname]["maintext"]=val.__doc__
                    doc[iname]["methods"]={}
                    doc[iname]["signals"]={}
                doc[iname]["signals"][mname]={}
                sig=dbus.Signature(mval.__dict__["_dbus_signature"])
                argspec=inspect.getargspec(mval)
                args=', '.join(map(lambda tup: str(tup[0])+": "+tup[1], zip(sigin,argspec[0][1:]))) # chop off self
                doc[iname]["signals"][mname]["sig"]=args
                doc[iname]["signals"][mname]["text"]= mval.__doc__


if sys.argv[2][:17]== "--generate-order=":
    order=file(sys.argv[2][17:],'w')
    order.write('\n'.join(doc.keys()))
    sys.exit(0)
else:
    print '<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.0 Transitional//EN" "http://www.w3.org/TR/xhtml1/DTD/xhtml1-transitional.dtd">'
    print '<html xmlns="http://www.w3.org/1999/xhtml" xml:lang="en" lang="en">'
    print '<head>'
    print '<title>Telepathy: D-Bus Interface Specification</title>' # inspectmod.__name__,'</title>'
    print '<link rel="stylesheet" type="text/css" media="screen" href="style.css" />'
    print '</head>'
    print '<body>'
    print '<div class="topbox">Telepathy</div>'

#    print '<div class="sidebar">'
#    order = file(sys.argv[2])
#    for name in order:
#        name = name[:-1]
#        name.strip()
#        pretty = name.replace('org.freedesktop.Telepathy', '')
#        print '  <a href="#%s">%s</a><br />' % (name, pretty)
#    print '</div>'

    print '<p><b>Please note that this is a draft specification and is subject to change without notice.</b></p>'

    order=file(sys.argv[2])
    for name in order:
        name=name[:-1]
        name.strip()
        print '<a name="%s"></a>' % name
        print '<h1>'+name+'</h1>'
        print '<pre>', doc[name]["maintext"], '</pre>'

        if len(doc[name]["methods"]) > 0:
            print '<h2>Methods:</h2>'
            for method in doc[name]["methods"].keys(): 
                print '<div class="method">'
                print '<h2>%s ( %s ) -> %s</h2>' % (method,doc[name]["methods"][method]["in_sig"], doc[name]["methods"][method]["out_sig"])
                print '<pre>', doc[name]["methods"][method]["text"], '</pre>'
                print '</div>'
        else:
            print '<p>Interface has no methods.</p>'

        if len(doc[name]["signals"]) > 0:
            print '<h2>Signals:</h2>'
            for signal in doc[name]["signals"].keys(): 
                print '<div class="signal">'
                print '<h2>%s ( %s )</h2>' % (signal,doc[name]["signals"][signal]["sig"])
                print '<pre>', doc[name]["signals"][signal]["text"], '</pre>'
                print '</div>'
        else:
            print '<p>Interface has no signals.</p>'

    print '</body></html>'

    sys.exit(0)
