#!/usr/bin/php -f
<?php
// Require package php5-cli

define('IN_PHPBB', true);
$phpEx = "php";
$phpbb_root_path = "/usr/share/phpbb3/www/";

set_include_path(get_include_path().PATH_SEPARATOR.$phpbb_root_path);

include('config.php');
include('common.php');
include('includes/functions_admin.php');

global $cache;
$cache->purge();

// Clear permissions
$auth->acl_clear_prefetch();
cache_moderators();

add_log('admin', 'LOG_PURGE_CACHE');
?>
PHPBB cache cleared!
