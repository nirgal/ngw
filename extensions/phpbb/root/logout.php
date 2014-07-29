<?php
    if (!$_SERVER['PHP_AUTH_USER']) {
        header('401 logout acknoledgement needed');
        header('WWW-Authenticate: Basic realm="ngw"');
        echo("Déconextion NON CONFIRMEE.");
        die();
    }

?>
<html>
<title>Déconnextion réussie.</title>
<h1>Déconnexion réussie.</h1>
</html>
