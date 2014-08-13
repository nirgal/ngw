$=django.jQuery;

function dump(o) {
    var txt = "";
    for (var k in o)
        txt+=k+"="+(""+o[k]).replace(/\n/g, " ")+"<br>";
    document.writeln("<hr>"+txt);
}

function check_footer_bottom() {
    min_height = document.body.clientHeight - $('#header').outerHeight() - $('#footer').outerHeight(); // - $('.breadcrumbs').outerHeight();
    // remove messages:
    min_height -= $('.messagelist').outerHeight();
    // remove margins:
    min_height -= $('#content').outerHeight(true) - $('#content').outerHeight(false);
    if (min_height > 0)
        $('#content').css('min-height', min_height+'px');
}

$(document).ready(check_footer_bottom);
$(window).resize(check_footer_bottom);


//--------------- Ajax

ALLOW_ERROR_MESSAGE=true;

function get_XMLHttpRequest() {
    if(window.XMLHttpRequest)
        try {
            return new XMLHttpRequest();
        } catch(e) {}
    alert("ERROR: Your browser doesn't support XMLHttpRequest! Get a real browser please.");
    return null;
}

function ajax_load_innerhtml(element_id, url) {
    req = get_XMLHttpRequest();
    if (!req)
        return;
    document.getElementById(element_id).innerHTML = "<img src='/static/ngw/loading.gif' align=middle> L O A D I N G . . . ";
    req.element_id = element_id;
    req.onreadystatechange = function () {
        if (req.readyState == 4) {
            if (req.status==200 || ALLOW_ERROR_MESSAGE)
                document.getElementById(req.element_id).innerHTML = req.responseText;
            else
                alert("There was a problem retrieving the XML data:\n" + req.statusText);
        }
    };
    req.open("GET", url, true);
    req.send(null);
}

/* Single quote a string, escaping as needed: */
function escape_quote(str) {
    return "'" + str.replace(/\\/g, '\\\\').replace(/'/g, "\\'") + "'";
}

