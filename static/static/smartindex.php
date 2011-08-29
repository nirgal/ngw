<?php

function getfileextension($filename) {
    $dotpos = strrpos($filename, ".");
    if ($dotpos === FALSE)
        return "";
    return substr($filename, $dotpos+1);
}

$mimetypes=array(
    "gif" => "image",
    "jpg" => "image",
    "jpeg" => "image",
    "png" => "image",
    "txt" => "text",
    "htm" => "text",
    "html" => "text",
    "php" => "text",
    "mp3" => "sound",
    "avi" => "video",
    "mov" => "video",
    "mp4" => "video",
    "mpg" => "video",
    "mpeg" => "video",
    "zip" => "compressed",
    "gz" => "compressed",
    "tgz" => "compressed",
    "bz2" => "compressed");



function getmimetype($filename) {
    if (is_dir($filename))
        return "folder";
    global $mimetypes;
    $ext = strtolower(getfileextension($filename));
    return $mimetypes[$ext];
}

$icons=array(
    "image" => "image2",
    "text" => "text",
    "sound" => "sound",
    "video" => "movie",
    "folder" => "folder",
    "debian" => "deb",
    "compressed" => "compressed");

function mime_to_icon($mimetype) {
    global $icons;
    $mimeicon = $icons[$mimetype];
    if ($mimeicon)
        return $mimeicon;
    return "unknown";
}

function getBeautifullSize($size) {
    if ($size<1024) {
        $result = strval($size)." B";
    } else if ($size<1024*1024) {
        $kb = (int)($size/1024);
        $result = strval($kb);
        if ($kb<10) {
            $firstDecimal = (int)(($size%1024)*10/1024);
            if ($firstDecimal!=0)
                $result .= '.'.$firstDecimal;
        }
        $result .= " kB";
    } else if ($size<1024*1024*1024) {
        $mb = (int)($size/(1024*1024));
        $result = strval($mb);
        if ($mb<10) {
            $firstDecimal = (int)(($size%(1024*1024))*10/(1024*1024));
            if ($firstDecimal!=0)
                $result .= '.'.$firstDecimal;
        }
        $result .= " MB";
    } else {
        $gb = (int)($size/(1024*1024/1024));
        $result = strval($gb);
        if ($gb<10) {
            $firstDecimal = (int)(($size%(1024*1024*1024))*10/(1024*1024*1024));
            if (firstDecimal!=0)
                $result .= '.'.$firstDecimal;
        }            
        $result .= " GB";
    }
    
    return $result;
}

function get_thumb_url($curentdir, $filename) {
	$thumbdir = dirname($filename).'/.ngw.thumbs640480/'.basename($filename);
	if (file_exists($thumbname) && filemtime($thumbname)>=filemtime($filename))
		return $thumbname;
	else
		return "/static/iconify.php?id=".htmlspecialchars(urlencode($curentdir.$filename));
}


//var_dump($_SERVER);
$curentdir = $_SERVER['REQUEST_URI'];
$qmpos = strpos($curentdir, "?");
if ($qmpos !== FALSE)
    $curentdir = substr($curentdir, 0, $qmpos);
$curentdir = urldecode($curentdir);
//echo 'curentdir=' . $curentdir;
chdir(getcwd().'/..'.$curentdir); // we need to remove static from getcwd
//echo 'dir=' . getcwd() .'<br>';
$filelist = glob("*");
$filelistUpper = array_map('strtoupper', $filelist);
array_multisort($filelistUpper, SORT_ASC, SORT_STRING, $filelist);

$array_by_type = array();
foreach ($filelist as $num => $filename) {
    $mimetype = getmimetype($filename);
    if (!array_key_exists($mimetype, $array_by_type))
        $array_by_type[$mimetype] = array();
    $array_by_type[$mimetype][] = $filename;
}

$mode = $_REQUEST['mode'];
if ($mode=='diaporama1') {
	//setlocale('LC_ALL', 'en_GB.UTF-8');
	//mb_internal_encoding('UTF-8');
	//mb_http_output('UTF-8');
	$utf8_curentdir = utf8_decode($curentdir);
    header("Content-Type: text/html; charset=utf-8");
    $num = $_REQUEST['num'];
    if (!$num)
        $num=0;
    $filename = $array_by_type['image'][$num];
    if ($num<count($array_by_type['image'])-1)
        header("Refresh: 15;url=https://".$_SERVER['HTTP_HOST'].$utf8_curentdir.'?mode=diaporama1&num='.($num+1));
    else
        header("Refresh: 15;url=https://".$_SERVER['HTTP_HOST'].$utf8_curentdir.'?mode=diaporama1');
    echo '<title>'.$curentdir.' - picture '.$num.'</title>';
    echo '<link rel=stylesheet href="/static/diapo.css">';
    echo '<div style="text-align:center;">';
	//echo("url=".$_REQUEST['HTTP_HOST']);
    echo '<a href="." target=_top>Index</a> ';
    echo '<center>';
    echo '<table id=imgcontain>';
    echo '<tr>';
    echo '<td>';
    if ($num>0)
        echo '<a href="?mode=diaporama1&num='.($num-1).'"><img src="/static/left.png" height=30 width=30 alt="Précédent"></a>';
    echo '<td>';
    echo '<a href="'.htmlspecialchars($filename).'" target=_top><img src="'.get_thumb_url($curentdir.$filename).'"/></a><br/>';
    echo '<td>';
    if ($num<count($array_by_type['image'])-1)
        echo '<a href="?mode=diaporama1&num='.($num+1).'"><img src="/static/right.png" height=30 width=30 alt="Suivant"></a>';
    echo '</table>';
    echo '</div>';

} else if ($mode=='diaporama') {
	echo '<frameset rows="*,170" noresize border=0>'; // 20 px for scrollbar
	echo "<frame name=big src='$currentdir?mode=diaporama1'>";
	echo "<frame name=thumbs src='$currentdir?mode=diaporama_rowframe'>";
	echo '</frameset>';
} else if ($mode=='diaporama_rowframe') {
    echo '<body style="margin:0;">';
    echo '<link rel=stylesheet href="/static/diapo.css">';
	echo '<div style="height:150px;"><nobr>';
	$num=0;
    foreach($array_by_type['image'] as $filename) {
        //echo "<a href='".htmlspecialchars($curentdir)."?mode=diaporama1&num=".$num."' target=big><img src='/static/iconify.php?id=".htmlspecialchars(urlencode($curentdir.$filename))."' height=150/></a>";
        //echo "<a href='".htmlspecialchars($curentdir)."?mode=diaporama1&num=".$num."' target=big><img src='".get_thumb_url($curentdir.$filename)."' height=150/></a>";
        echo "<a href='?mode=diaporama1&num=".$num."' target=big><img src='".get_thumb_url($curentdir.$filename)."' height=150/></a>";
		$num++;
    }
	echo '</nobr></div>';
} else {
    echo '<title>Index of '.$curentdir.'</title>';
    echo '<h1>Index of '.htmlspecialchars($curentdir).'</h1>';
    echo '<table>';
    echo '<tr><th><th>Nom<th>Taille';
    echo '<tr><th colspan=3><hr/>';
    if (array_key_exists('image', $array_by_type)) {
        echo '<tr><td><td><a href="?mode=diaporama"><b>Voir ce dossier en diaporama<b></a><br/>';
        echo '<tr><td><td><a href="?mode=diaporama1"><b>Voir ce dossier en diaporama<b> (sans frame)</a><br/>';
	}
    
    echo '<tr><td><img src="/icons/back.gif"><td><a href="..">Dossier parent</a><br>';
    foreach ($array_by_type as $mimetype => $filenames) {
        foreach ($filenames as $filename) {
            echo '<tr><td><img src="/icons/'.mime_to_icon($mimetype).'"/>';
            echo '<td><a href="'.htmlspecialchars($filename).'">'.htmlspecialchars($filename).'</a><br/>';
            if ($mimetype!='folder') {
                $fullfilename = '/usr/lib/ngw/static/'.$curentdir.$filename;
                echo '<td align=right>'.getBeautifullSize(filesize($fullfilename));
            }
        }
    }
    echo '<tr><th colspan=3><hr/>';
    echo '</table>';
}
?>
