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


/* Single quote a string, escaping as needed: */
function escape_quote(str) {
    return "'" + str.replace(/\\/g, '\\\\').replace(/'/g, "\\'") + "'";
}

