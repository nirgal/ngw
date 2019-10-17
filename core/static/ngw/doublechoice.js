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
