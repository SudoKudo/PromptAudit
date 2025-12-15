<h1>Root Administration Area</h1>

<p>Please login with your root password to access the root administration area. Your root password can be reset manually in config.php.</p>

<form method="POST" action="index.php">
<? if(!$user_loggedin) { ?>
Username: <input type="text" name="username" /><br />
<? } ?>
Password: <input type="password" name="password" /><br />
<input type="submit" name="submit" value="Submit" />
</form>
