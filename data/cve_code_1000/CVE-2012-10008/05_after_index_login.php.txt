<h1>Root Administration Area</h1>

<p>Please login with your root password to access the root administration area. Your root password can be reset manually in config.php.</p>

<form method="POST" action="index.php">
<table class="center"><tr>
<? if(!$user_loggedin) { ?>
<td>Username <input type="text" name="username" /></td>
<? } ?>
<td>Password <input type="password" name="password"></td>
<td><input type="submit" name="submit" value="Submit"></td>
</tr></table>
</form>
