<h1>Administrator Page</h1>

<p>Log in with the administrator username and password. These are added through <b>Admin Management</b> in the root administration section. If you do not know your username and password, then you should contact your root administrator.</p>

<table>
	<tr>
		<form method="POST" action="index.php">
		<table>
			<tr>
				<td>Username:</td>
				<td><input type="text" name="username"/></td>
			</tr>
			<tr>
				<td>Password:</td>
				<td><input type="password" name="password"/></td>
			</tr>
			<tr>
				<td colspan="2"><input type="submit" value="Submit" align="center"/></td>
			</tr>
		</table>
		</form>
	</tr>

	<?
	if(isset($message) && $message != "") {
	?>
		<tr><td colspan="2"><?= $message ?></td></tr>
	<?
	}
	?>
</table>
