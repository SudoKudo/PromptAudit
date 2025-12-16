<h1>Club management</h1>

<p>Here, you can edit settings for your club. View time is the time at which your club will be available for addition into a user's supplement list. Open time is the time when the club supplement can be submitted. Close time is the submission deadline. The number of recommendations field is the required number of recommendations for your club; there is no upper limit on the number that can be submitted, except the maximum number of recommendations a user can request (set in the configuration file).</p>

<h3>Club settings</h3>
<form method="post" action="man_club.php">
<table>
<tr>
	<td colspan="2">Description</td>
<tr>
	<td colspan="2"><textarea name="description"><?= $description ?></textarea></td>
</tr>
<tr>
	<td>View time</td>
	<td><input type="text" name="view_time" value="<?= date('m/d/y H:i:s', $view_time) ?>" /> MM/DD/YY (hh:mm:ss)</td>
</tr>
<tr>
	<td>Open time</td>
	<td><input type="text" name="open_time" value="<?= date('m/d/y H:i:s', $open_time) ?>" /></td>
</tr>
<tr>
	<td>Close time</td>
	<td><input type="text" name="close_time" value="<?= date('m/d/y H:i:s', $close_time) ?>" /></td>
</tr>
<tr>
	<td>Number of recommenations</td>
	<td><input type="text" name="num_recommend" value="<?= $num_recommend ?>" /></td>
</tr>
<tr>
	<td colspan="2"><input type="submit" value="Update" /></td>
</tr>
</table>
</form>
