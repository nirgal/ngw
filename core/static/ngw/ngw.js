/*$=django.jQuery;*/

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
    else
	return; /* can't do it :( */

    if (!$('#footer').outerHeight())
        return; // No footer

    min_height = theHeight - $('#header').outerHeight() - $('#footer').outerHeight();

    // remove breadcrumbs:
    removeh = $('.breadcrumbs').outerHeight();
    if (!isNaN(removeh))
        min_height -= removeh;

    // remove submenu:
    removeh = $('#submenucontainer').outerHeight();
    if (!isNaN(removeh))
        min_height -= removeh;

    // remove messages:
    removeh = $('.messagelist').outerHeight();
    if (!isNaN(removeh))
        min_height -= removeh;

    // remove content margins:
    //SHOULD WORK, BUT DOESN'T: min_height -= $('#content').outerHeight(true) - $('#content').outerHeight(false);
    min_height -= 40; // margin of content
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

function inline_edit_membership(title, cig_url, membership, note) {
    $('#membership_edit h3').html(title);
    $('#membership_edit form').attr('action', cig_url + '/membershipinline');
    $('#membership_edit_more').attr('href', cig_url + '/membership');
    $('#membership_edit_form input[name=membership_i]').prop('checked', membership.indexOf('i') != -1)
    $('#membership_edit_form input[name=membership_m]').prop('checked', membership.indexOf('m') != -1)
    $('#membership_edit_form input[name=membership_d]').prop('checked', membership.indexOf('d') != -1)
    $('#membership_edit_form input[name=membership_D]').prop('checked', membership.indexOf('D') != -1)
    $('#membership_edit_form input[name=note]').val(note);
    if (membership.indexOf('i') != -1 || membership.indexOf('m') != -1 || membership.indexOf('d') != -1 || membership.indexOf('D') != -1)
        $('#membership_edit_form input[name=note]').removeAttr('disabled');
    else {
        $('#membership_edit_form input[name=note]').prop('disabled', 'true');
    }
    $('#membership_edit').show();
}

function inline_edit_membership_close() {
    $('#membership_edit').hide();
}

//----------------------------
// contact list with autocompletion

$(document).ready(
	function() {
		$( "#qsearch" ).autocomplete({
			source: autocompleteurl,
			select: function(event, ui) {
				//$("#qsearch").val(ui.item.label);
				document.location = '/contacts/' + ui.item.value + '/';
				//$("#header_quicksearch").submit(); 
				}
		});
	}
);



//----------------------------
// toggle image sizes. It's applied on the container. It works for all square nodes.
var imagefile_size_small = '50px'; // TODO: read from style
var imagefile_size_big = '200px';
function toggle_imagefield_sizes(node) {
	var style = node.style;
	if (style.width == imagefile_size_big)
		style.width = style.height = imagefile_size_small;
	else
		style.width = style.height = imagefile_size_big;
}

//---------------------------
// Modal messages:

function ngw_modal(html) {
    document.getElementById('ngw_modal_container').style.display='block';
    html += "<h3><a onclick='ngw_modal_close();' class=button>"+gettext("Close")+"</a></h3>";
    document.getElementById('ngw_modal_message').innerHTML = html;
}
function ngw_modal_close() {
    document.getElementById('ngw_modal_container').style.display='none';
}

function icon_busy_detail2() {
    for (let e of document.getElementsByClassName('iconbusy')) {
        e.addEventListener('click', function(evt) {
	    if (!('contactid' in e.dataset) || !('groupid' in e.dataset)) {
		console.log('No data in icon_busy_detail2 handler')
		return;
            }

            let contactid = e.dataset['contactid'];
	    let groupid = e.dataset['groupid'];
            let xhr = new XMLHttpRequest();
            let url = '/contacts/' + contactid + '/unavail_detail/' + groupid;
            xhr.open('GET', url);
            xhr.responseType = 'json';
            xhr.onload = function() {

                if (xhr.status != 200) {
                    ngw_modal(gettext("Sorry, personnal calendar can't be loaded. Please try again later."));
                    return;
                }

                ngw_modal(xhr.response.result);
            }
            xhr.send();
            ngw_modal(gettext("Loading personnal calendar..."));
        });
    }
}
