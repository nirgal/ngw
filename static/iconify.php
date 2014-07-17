<?php

/*
Security is not enforced here, beyond not writing where we should not.
After the thumbnail is checked for update, we just send a redirect.
.htaccess from upper level does the stuff.
TODO: Do not create thumbnail if we are browsing the thumbnail dir.
*/
$MEDIA_ROOT = '/usr/lib/ngw/media/';
$MEDIA_URL = '/media/';

// iconify
if (!extension_loaded('gd'))
	echo("Error lib GD not loaded!");


$id = $_REQUEST["id"];
// Check that $id starts with MEDIA_URL and remove it
if (substr($id, 0, strlen($MEDIA_URL)) != $MEDIA_URL) {
    echo ("URL should start with $MEDIA_URL");
    die(1);
}
//echo "currentdir=$currentdir<br>";
$filename = $MEDIA_ROOT . substr($id, strlen($MEDIA_URL));

if (strpos($filename, '..') != FALSE) {
    echo("Access denied");
    die(1);
}

$thumbdir=dirname($filename).'/.ngw.thumbs640480';
$thumbname=$thumbdir.'/'.basename($filename);
if (!file_exists($thumbname) || filemtime($thumbname)<filemtime($filename)) {
	/* thumb does not exists yet, or is outdated */
	list($width, $height, $type, $attr) = getimagesize($filename);
	
	// target is a rectangle 640x480
	$small_size_w = 640;
	$zoomfactor=$width/640;
	$small_size_h = $height/$zoomfactor;
	if ($small_size_h>480) {
		$small_size_h = 480;
		$zoomfactor=$height/480;
		$small_size_w = $width/$zoomfactor;
	}
	
	$result_preload = imagecreatefromstring(file_get_contents($filename));
	$result = imagecreatetruecolor ($small_size_w,$small_size_h); 
	
	imagecopyresampled($result, $result_preload, 0,0, 0,0, $small_size_w,$small_size_h, $width, $height);
	
	// check target directory exists
	#echo $thumbdir;
	#die();
	if (!file_exists($thumbdir))
		if (!mkdir($thumbdir)) {
			echo('Error while creating folder: '.$thumbdir);
			die();
		}
	imagejpeg  ($result, "$thumbname", 70);
}
header ("302 Use cache");
header ("Location: ".dirname($id)."/.ngw.thumbs640480/".basename($id));
?>
