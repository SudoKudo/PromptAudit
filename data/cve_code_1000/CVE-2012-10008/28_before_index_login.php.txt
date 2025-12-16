<h1>Administrator Page</h1>

<p>Log in with the administrator username and password. These are added through <b>Admin Management</b> in the root administration section. If you do not know your username and password, then you should contact your root administrator.</p>

<div id="admin_table">
<div id="admin_login">
<table cellpadding="0" cellspacing="0" width=100%>
<tr id="admin_login"><td id="admin_login"><h2>Log In</h2></td></tr>
<tr id="admin_form">

	<form method="POST" action="index.php">
	<table>
	<tr id="admin_username">
	<td><p id="admin_username" align="right">Username:</p></td>
	<td><input type="text" name="username"/></td>
	</tr>
	<tr id="admin_password">
	<td><p id="admin_password" align="right">Password:</p></td>
	<td><input type="password" name="password"/></td>
	</tr>
	<tr id="admin_submit">
	<td colspan="2" align="right"><input type="submit" value="Submit" align="center"/></td>
	</tr>
	</table>
	</form>

	</tr>

	<?
	if(isset($message) && $message != "") {
	?>
		<tr id="admin_login_message"><td id="admin_login_message" colspan="2"><p id="admin_login_message" class="center"><?= $message ?></p></td></tr>
	<?
	}
	?>


	</table>
	</div>
	</div>
