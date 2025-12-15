export default class Sanitize {
    constructor() {
    }

    /**
     * This function replaces all instances of lt and gt with their
     * HTML entity.
     */
    htmlSanitize(html) {
        html = html.replace(/</g, '&lt;');
        html = html.replace(/>/g, '&gt;');

        return html;
    }
}
