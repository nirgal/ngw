/**
 * Converts a string into an html printable string.
 * Default is to replace only essential characters "&" and "<".
 *
 * @param {string} txt
 * @param {RegExp} [re=/[&<]/g] Characters to be escaped.
 * @return {string}
 */
function htmlEscape(txt, re=/[&<]/g) {
    return txt.replace(re, c => '&#' + c.charCodeAt(0) + ';');
}


function setupInputDropFiles(fileInput) {
    let inputNodeId = fileInput.id;
    let form = dropDomToForm(fileInput);

    let dropZone = document.createElement('div');
    dropZone.setAttribute('id', inputNodeId + '_drop_zone');
    dropZone.setAttribute('class', 'drop_zone');
    dropZone.innerHTML = gettext('Drop files here');
    fileInput.parentNode.appendChild(dropZone);

    dropZone.addEventListener('dragover', handleDragOverCopy);
    dropZone.addEventListener('drop', onFileDrop, false);

    form.globalFiles = [];

    let fileList = document.createElement('div');
    fileList.setAttribute('id', inputNodeId + '_filelist');
    fileList.setAttribute('class', 'filelist');
    fileInput.parentNode.appendChild(fileList);

    fileInput.parentNode.removeChild(fileInput);

    form.onsubmit = async (evt) => {
        evt.preventDefault();

        let formData = new FormData(form);
        for (let file of form.globalFiles) {
            formData.append('files', file);
        }

        let response = await fetch('?'/*form.action*/, {
            method: 'POST',
            body: formData,
            responseType: 'json',
            headers: {
                'X-Requested-With': 'XMLHttpRequest',
                Accept: 'application/json'
            }
        });

        if (response.ok) { // response code 200
            //let result = await response.text();
            let result = await response.json();
            if (result.has_error) {
                let alertmsg = '';
                for (let propname in result.errors) {
                    for (let err of result.errors[propname]) {
                        alertmsg += propname + ": " + err.message + "\n";
                    }
                }
                alert(alertmsg);
            }
            else
                document.location = result.url;
        }
    };
}

// returns the parent form
function dropDomToForm(domElem) {
    for (let e = domElem; e; e = e.parentNode)
        if (e.tagName === 'FORM')
            return e;
}

function handleDragOverCopy(evt) {
    evt.stopPropagation();
    evt.preventDefault();
    evt.dataTransfer.dropEffect = 'copy';  // nice 'copy' cursor
}

function onFileDrop(evt) {
    evt.stopPropagation();
    evt.preventDefault();

    let form = dropDomToForm(evt.target);
    let dropId = evt.target.id;
    let domInput = document.getElementById(dropId.substr(0, dropId.length - "_drop_zone".length));

    for (let file of evt.dataTransfer.files) {  // FileList object.
        form.globalFiles.push(file);
    }
    refreshFileList(form);
}

function refreshFileList(form) {
    let lines = [];
    for (let i in form.globalFiles) {
        let file = form.globalFiles[i];
        let line = '<strong>' + htmlEscape(file.name) + '</strong>';
        let attrs = [];
        if (file.type)
            attrs.push(htmlEscape(file.type));
        if (file.size)
            attrs.push(+file.size + ' bytes');
        if (attrs)
            line += ' ( ' + attrs.join(', ') + ' )';
        line += ` <img src="/static/ngw/icon_trash.svg" alt=Remove title=Remove class=removable data-fileindex=${i} style="cursor:pointer;">`;

        lines.push('<li>' + line + '</li>');
    }
    let divFileList = form.getElementsByClassName('filelist')[0];
    divFileList.innerHTML = '<ul>' + lines.join('') + '</ul>';

    for (let domelem of document.getElementsByClassName('removable')) {
        domelem.addEventListener('click', removeFile);
    }
}

function removeFile(evt) {
    let fileindex = +evt.target.dataset.fileindex;
    let form = dropDomToForm(evt.target);
    form.globalFiles.splice(fileindex, 1);
    refreshFileList(form);
}

window.addEventListener('load', function() {
    for (let msginput of document.getElementsByClassName('inputfile_nicezone'))
        setupInputDropFiles(msginput);
});

