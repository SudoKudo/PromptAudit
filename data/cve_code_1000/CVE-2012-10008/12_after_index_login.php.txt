<h1>Administrator Page</h1>

<p>Log in with the administrator username and password. If you do not have an adminstrative username, please ask your root manager to add you. If you have forgotten your username and/or password, contact your root administrator to reset your password.</p>
<br />
<table width=60% class="log_in">
	<form method="POST" action="index.php">
	<? if(!$user_loggedin) { ?>
	<tr>
		<td width=20%><p class="name">Username</p></td>
		<td align="right"><input type="text" name="username"/></td>
	</tr>
	<? } ?>
	<tr>
		<td><p class="name">Password</p></td>
		<td align="right"><input type="password" name="password"/></td>
	</tr>
	<tr>
		<td><p class="name">Club:</p></td>
		<td align="right"><select name="club">
		<? foreach($clubs as $club_id => $club_name) { ?>
			<option value="<?= $club_id ?>"><?= $club_name ?></option>
		<? } ?>
		</select></td>
	</tr>
	<tr class="club_info">
		<td colspan="2" align="right"><input type="submit" value="Log In" class="positive"/></td>
	</tr>
	</form>
</table>
