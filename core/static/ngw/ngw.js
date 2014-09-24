$=django.jQuery;

function dump(o) {
    var txt = "";
    for (var k in o)
        txt+=k+"="+(""+o[k]).replace(/\n/g, " ")+"<br>";
    document.writeln("<hr>"+txt);
}

function check_footer_bottom() {
    // Get the body heigth (with quirks mode support)
    if (window.innerHeight)
        theHeight=window.innerHeight;
    else if (document.documentElement && document.documentElement.clientHeight)
        theHeight=document.documentElement.clientHeight;
    else if (document.body)
        theHeight=document.body.clientHeight;

    min_height = theHeight - $('#header').outerHeight() - $('#footer').outerHeight();
    // remove breadcrumbs:
    min_height -= $('.breadcrumbs').outerHeight();
    // remove submenu:
    min_height -= $('#submenucontainer').outerHeight();
    // remove messages:
    min_height -= $('.messagelist').outerHeight();

    // remove margins:
    min_height -= $('#content').outerHeight(true) - $('#content').outerHeight(false);
//alert('margin='+($('#content').outerHeight(true) - $('#content').outerHeight(false)));
    if (min_height > 0)
        $('#content').css('min-height', min_height+'px');
}

$(document).ready(check_footer_bottom);
$(window).resize(check_footer_bottom);


/* Single quote a string, escaping as needed: */
function escape_quote(str) {
    return "'" + str.replace(/\\/g, '\\\\').replace(/'/g, "\\'") + "'";
}

//------------------------------
// Inline membership edition

function inline_edit_membership(title, cig_url, membership) {
    $('#membership_edit h3').html(title);
    $('#membership_edit form').attr('action', cig_url + '/membershipinline');
    $('#membership_edit_more').attr('href', cig_url + '/membership');
    $('#membership_edit_form input:radio[name=membership]').val([membership]);
    $('#membership_edit').show();
}

function inline_edit_membership_close() {
    $('#membership_edit').hide();
}
