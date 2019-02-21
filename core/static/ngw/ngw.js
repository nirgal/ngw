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
// double choices show/hide refresh

function doublechoice_show(baseid, init_auto)
{
    var i = 0;
    var nb_consecutive_empty = 0;
    //alert('Refreshing show/hide');
    while(1) {
        var col1 = $('#'+baseid+'_'+i+' option:selected').val();
        var col2 = $('#'+baseid+'_'+(i+1)+' option:selected').val();
        if (typeof(col1) == 'undefined')
            break;
        if (init_auto) {
            // On first call, setup the onchange handlers
            $('#'+baseid+'_'+i).attr('onchange', "doublechoice_show('"+baseid+"',0)");
            $('#'+baseid+'_'+(i+1)).attr('onchange', "doublechoice_show('"+baseid+"',0)");
        }
        if (col1 || col2) {
            nb_consecutive_empty = 0;
        } else {
            nb_consecutive_empty++;
            if (nb_consecutive_empty > 1) {
                $('#'+baseid+'_'+i).hide();
                $('#'+baseid+'_'+(i+1)).hide();
            } else {
                $('#'+baseid+'_'+i).show();
                $('#'+baseid+'_'+(i+1)).show();
            }
        }

        i+=2;
        if (i>=100) {
            alert('Javascript error in doublechoice_show');
            break;
        }
    }
    return false;
}


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
