<?php
// iconify
if (!extension_loaded('gd'))
	echo("Error lib GD not loaded!");

$id = stripslashes($_REQUEST["id"]);
//TODO
//$_SERVER[DOCUMENT_ROOT] == /usr/lib/ngw/extensions/phpbb/static/ 
$filename = "/usr/lib/ngw/static/".$id;
if (strstr($filename, "..")) {
	echo('error'); // HACK ATTEMPT!
	die();
}
$thumbdir=dirname($filename).'/.ngw.thumbs640480';
$thumbname=$thumbdir.'/'.basename($filename);
if (!file_exists($thumbname) || filemtime($thumbname)<filemtime($filename)) {
	/* thumb does not exists yet */
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
	if (!file_exists(thumbdir))
		mkdir($thumbdir);
	imagejpeg  ($result, "$thumbname", 70);
}
header ("302 Use cache");
header ("Location: ".dirname($id)."/.ngw.thumbs640480/".basename($id));
?>
