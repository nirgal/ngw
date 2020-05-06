/*
 * mimsg - MIme MeSsaGe javascript library / module
 * (C) 2020
 *
 * This program is free software: you can redistribute it and/or modify
 * it under the terms of the GNU General Public License as published by
 * the Free Software Foundation, either version 3 of the License, or
 * (at your option) any later version.
 *
 * This program is distributed in the hope that it will be useful,
 * but WITHOUT ANY WARRANTY; without even the implied warranty of
 * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
 * GNU General Public License for more details.
 *
 * You should have received a copy of the GNU General Public License
 * along with this program.  If not, see <http://www.gnu.org/licenses/>.
 */

/*
RFC822: "Return-Path", "Received", "Date",  "From",  "Subject",  "Sender", "To", "cc", etc.
RFC2045: "Mime-Version", "Content-Type"
RFC2183: "Content-Disposition" (for multipart items)
RFC1341: "Content-Transfer-Encoding" (base64, quoted-printable, 8Bit, 7bit, binary, x-*)
Rfc3676: Format=flowed; DelSp=yes (TODO)
*/

// Comments should use https://jsdoc.app/

const rfc5322_max_line_length = 998;  // excluding CRLF


/**
 * Search an array inside an array.
 * indexOf can only handle one item at a time on TypedArray.
 * Usefull to find boundaries in 8 bits messages.
 *
 * @param {Array}  haystack
 * @param {Array}  needle
 * @param {number} [start=0]
 * @return {number}
 */
export function arrayIndexOfArray(haystack, needle, start = 0) {
    const lh = haystack.length, ln = needle.length;

    while (start <= lh - ln) {
        // quick search first item of needle
        var i = haystack.indexOf(needle[0], start);
        if (i === -1)
            return -1; // not found

        // good. Now check needle is actually there:
        var found = true;
        for (var j = 1; j < ln; j++) {
            if (haystack[i + j] != needle[j]) {
                found = false;
                break; // No use looking further
            }
        }
        if (found)
            return i;
        start = i + 1;
    }
    return -1;
}


/**
 * Converts a string into an html printable string.
 * Default is to replace only essential characters "&" and "<".
 *
 * @param {string} txt
 * @param {RegExp} [re=/[&<]/g] Characters to be escaped.
 * @return {string}
 */
export function htmlEscape(txt, re=/[&<]/g) {
    return txt.replace(re, c => '&#' + c.charCodeAt(0) + ';');
}


/**
 * Convert an unicode string into an Uint8Array, using UTF-8 charset.
 */
export function textEncode(str) {
    const encoder = new TextEncoder();
    return encoder.encode(str);
}


/**
 * Decode an Uint8Array into an unicode string.
 */
export function textDecode(u8arr, charset='UTF-8') {
    const decoder = new TextDecoder(charset);
    return decoder.decode(u8arr);
}


/**
 * Convert a base64 string into a Uint8Array.
 */
function base64ToUint8Array(txt) {
    // txt is a string
    // returns a Uint8Array
    var str = window.atob(txt);
    var l = str.length;
    var arr = new Uint8Array(l);
    for (var i = 0; i < l; i++) {
        arr[i] = str.charCodeAt(i);
    }
    return arr;
}


/**
 * Convert a Uint8Array into a base64 string.
 */
function uint8ArrayToBase64(u8arr) {
    // u8arr is a Uint8Array
    // returns a string
    var str = '';
    var l = u8arr.length;
    for (var i = 0; i < l; i++) {
        str += String.fromCharCode(u8arr[i]);
    }
    return window.btoa(str);
}


/**
 * Convert a quoted printable string into a Uint8Array
 */
function quotedPrintableDecode(text) {
    const l = text.length;
    var u8arr = new Uint8Array(l);
    var iT /* in text*/, iA /* in array */ = 0;
    for (iT = 0; iT < l; iT++) {
        let c = text.charCodeAt(iT);
        if (c === 61) {  // '='
            let hexa = text.substr(iT + 1, 2);
            c = parseInt(hexa, 16);
            iT += 2;
            if (isNaN(c))
                continue;
        }
        u8arr[iA++] = c;
    }
    return u8arr.slice(0, iA);
}


/*
 * Returns the first charset in ['us-ascii', 'iso8859-1', 'utf-8'] that can
 * encode a string.
 * Unused because TextEncoder only supports UTF-8 !

function getShortestCharset(str) {
    let is7Bits = true;
    let l = str.length;
    for (let i = 0; i < l; i++) {
        let c = str.charCodeAt(i);
        if (c > 255)
            return 'utf-8';
        if (c > 127)
            is7Bits = false;
    }
    return is7Bits ? 'us-ascii' : 'iso8859-1';
}
*/

/**
 * Returns true if string can be ascii7 encoded
 */
function isString7bit(str) {
    for (let i = 0, l = str.length; i < l; i++) {
        let c = str.charCodeAt(i);
        if (c > 127)
            return false;
    }
    return true;
}


/**
 * Make sure end of lines use \r\n.
 *
 * @param {string} str A string using \r\n or \r or \n or \n\r or a single line
 * @return {string} String using \r\n
 */
export function normalizeCRLF(str) {
    const iN = str.indexOf('\n');
    const iR = str.indexOf("\r");

    if (iN === -1) {
        if (iR !== -1) {
            // \r only
            return str.replace(/\r/g, '\r\n');
        }
        // else no \r and no \n : noop
    } else {
        if (iR === -1) {
            // \n only
            return str.replace(/\n/g, '\r\n');
        } else if (iN < iR) {
            return str.replace(/\n\r/g, '\r\n');
        }
        // else iR < iN : Already using \r\n, noop
    }
    return str;
}


/**
 * Return a random string
 *
 * @param {number} [len=16]                                                                     - The length of the result
 * @param {string} [alphabet='ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789_'] - The possible letters
 * @return {string}
 */

export function randomId(len=16, alphabet='ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789_') {
    let res = '';
    for (let i = 0; i < len; i++)
        res += alphabet.charAt(Math.floor(Math.random() * alphabet.length));
    return res;
}

// FIXME: RFC2047 6.2 Display of 'encoded-word's
// Decoding and display of encoded-words occurs *after* a
// structured field body is parsed into tokens.  It is therefore
// possible to hide 'special' characters in encoded-words which, when
// displayed, will be indistinguishable from 'special' characters in the
// surrounding text.  For this and other reasons, it is NOT generally
// possible to translate a message header containing 'encoded-word's to
// an unencoded form which can be parsed by an RFC 822 mail reader.
// Hint: Kmail decodes
// =?ISO-8859-1?Q?T=3Cest?= <contact@onetime.info>
// into
// "T<est" <contact@onetime.info>

/**
 * Header.
 * @class
 */
class MiMsgHeader {
    constructor(name, value, attrs={}) {
        this.name = name;  // lower case
        this.value = value;  // decoded to utf-8
        this.attrs = attrs;  // only used by Content-* headers
    }

    /**
     * @constructs MiMsgHeader
     */
    static parse(line) {
        /* line is rfc822 unfolded, but with =?x?x?= encoded fragments */
        var i = line.indexOf(':');
        if (i === -1) {
            console.error('Invalid RFC822 header line without column: ' + line);
            return null;  // FIXME this will break later...
        }
        var name = line.substr(0, i).toLowerCase();
        var value = line.substr(i + 1);
        value = MiMsgHeader.parse_value(value);
        var result = new MiMsgHeader(name, value);
        if (name.startsWith('content-')) {
            const split = result.contentSplit();
            result.value = split[0];
            result.attrs = split[1];
        }
        return result;
    }


    /**
     * Decode a rfc2047 encoded fragment in the =?charset?encoding?str?= format
     *
     * @param {string} - Charset
     * @param {string} - Encoding 'B' or 'Q'
     * @param {string} - Text to be decoded
     * @return {string}
     * @example
     * // return 'Message chiffré'
     * decodeHeaderValueFragment('UTF-8', 'Q', 'Message_chiffr=c3=a9_GnuPG');
     */
    static decodeHeaderValueFragment(charset, encoding, str) {
        encoding = encoding.toUpperCase();
        let decoded;
        if (encoding === 'B') {
            // base64 encoded
            decoded = base64ToUint8Array(str);
        } else if (encoding === 'Q') {
            // quoted printable
            decoded = MiMsgHeader.decodeQuotedPrintable(str);
        } else {
            console.error("Maformed RFC2047 header: Unsupported encoding '" + encoding + '". Expected "B" or "Q"');
            return '';  // Displayed not attempted, see rfc2047 6.3
        }
        return textDecode(decoded, charset);  // Uint8Array -> str
    }


    static parse_value(raw) {
        /*
        This decodes the value of a mail header value, according to RFC2047.
        raw may be something like
        "=?UTF-8?Q?Message_chiffr=c3=a9_GnuPG?="
        */

        // This is almost .replace(/=?(.*)?(.*)?(.*)?=/, (orig, x, y, z) => decodeHeaderValueFragment(x, y z));
        // But white space is ignored between encoded, also:
        // RFC2047 tokens for charset & encoding excludes: CTLs + ' ()<>@,;:"/[]?.='
        // RFC2047 tencoded-text alphabet excludes CTLs + ' ?'
        const re = /=\?([^\0- ()<>@,;:"/[\]?.=]*)\?([^\0- ()<>@,;:"/[\]?.=]*)\?([^\0- ?]*)\?=/;
        let result = '';
        let lastIndex = 0;
        let found;
        while (found = raw.substr(lastIndex).match(re)) {
            let inBetween = raw.substr(lastIndex, found.index);
            if (!inBetween.match(/^[ \t\r\n]$/gm))
                result += inBetween;
            result += MiMsgHeader.decodeHeaderValueFragment(found[1], found[2], found[3]);
            lastIndex += found.index + found[0].length;
        }
        result += raw.substr(lastIndex);
/*
        var result = '';
        var i = 0;
        var afterEncoded = false;  // rfc2047 6.2: Ignore spaces between encoded words
        while (i < raw.length) {
            if (raw.substr(i, 2) === '=?') {
                if (afterEncoded) {
                    result = result.replace(/[ \t\r\n]*$/, '');  // remove empty spaces at the end
                }
                var j = raw.indexOf('?', i + 2);
                if (j === -1) {
                    console.error('Maformed RFC2047 header: Charset not found in ' + raw.substring(i));
                    result += raw.substr(i);
                    break;
                }
                var charset = raw.substring(i + 2, j);
                // TODO: remove the language as per rfc2231 section 7 (?)
                var k = raw.indexOf('?', j + 1);
                if (k === -1) {
                    console.error('Maformed RFC2047 header: Encoding not found in ' + raw.substring(i));
                    result += raw.substr(i);
                    break;
                }
                var encoding = raw.substring(j + 1, k);
                j = k;
                k = raw.indexOf('?=', j + 1);
                if (k === -1) {
                    console.error('Maformed RFC2047 header: Encoded text not terminated in ' + raw.substring(i));
                    result += raw.substr(i);
                    break;
                }
                var encoded = raw.substring(j + 1, k);
                i = k + 2;

                result += MiMsgHeader.decodeHeaderValueFragment(charset, encoding, encoded);
                afterEncoded = true;
            } else {
                var c = raw.charAt(i++);
                if (afterEncoded && ' \t\r\n'.indexOf(c) === -1) {
                    afterEncoded = false;
                }
                result += c;
            }
        }
*/


        // Cleaup spaces: trim left, deduplicate in the middle, trim right
        result = result.replace(/^[ \t\r\n]*/, '').replace(/[ \t\r\n]+/g, ' ').replace(/[ \t\r\n]*$/, '');
        return result;
    }


    /**
     * Decode quoted printable text as Uint8Array according to RFC2047, where "_" means space.
     *
     * @param {string} txt
     * @return {Uint8Array}
     */
    static decodeQuotedPrintable(txt) {
        // txt is a string
        // returns a Uint8Array
        var l = txt.length, arr = [];
        for (var i = 0; i < l;) {
            var c = txt.charCodeAt(i);
            if (c === 0x3d /*'='*/ && i + 2 < l) {
                var hex = parseInt(txt.substr(i + 1, 2), 16);
                arr.push(hex);
                i += 3;
            } else if (c === 0x5f /*'_'*/) {
                arr.push(0x20); // ' '
                i++;
            } else {
                arr.push(c);
                i++;
            }
        }
        var result = new Uint8Array(arr.length);
        result.set(arr);
        return result;
    }


    /**
     * Decode attribute value according to RFC2231.
     * @example
     * // returns 'Gérard'
     * MiMsgHeader.attributeDecodeRFC2231("ISO-8859-1''G%E9rard")
     */
    static attributeDecodeRFC2231(val) {
        var p1 = val.indexOf("'");
        var p2 = val.indexOf("'", p1 + 1);
        if (p1 === -1 || p2 === -1) {
            console.error('Invalid RFC2231 attribute value ' + val);
            return 'error';
        }
        var charset = val.substr(0, p1);
        var encoded = val.substr(p2 + 1);
        var l = encoded.length;
        var result = new Uint8Array(l);
        var lres = 0;
        for (var i = 0; i < l; i++) {
            var c = encoded.charCodeAt(i);
            if (c === 37) {  // '%'
                let cc = encoded.substr(i + 1, 2);
                cc = parseInt(cc, 16);
                result[lres++] = cc;
                i += 2;
            } else {
                result[lres++] = c;
            }
        }
        result = result.slice(0, lres);

        return textDecode(result, charset);
    }


    /**
     * Encode an attribute value according to RFC2231.
     * @param {string} - test
     * @return {string}
     * @example
     * // returns "UTF-8''G%C3A9rard"
     * MiMsgHeader.attributeEncodeRFC2231('Gérard')
     */
    static attributeEncodeRFC2231(str) {
        let u8arr = textEncode(str);
        let result = "UTF-8''";
        for (let i = 0, l = u8arr.length; i < l; i++) {
            let c = u8arr[i];
            if (c < 128 && c >= 32) {
                let cc = String.fromCharCode(c);
                // illegal chars: attribute-char in RFC 2231 section 7 + tspecials in RFC 2045 section 5.1
                if (!'*\'%()<>@,;\\\"/[]?='.includes(cc)) {
                    result += cc;
                    continue;
                }
            }
            result += '%';
            let hex = c.toString(16);
            if (hex.length === 1)
                result += '0';
            result += hex;
        }
        return result;
    }


    contentSplit() {
        // Token are parsed according to rfc2045
        // This is only for 'Content-*' headers
        // 'multipart/mixed; boundary="NEBIKbUAj980jV2K"' returns [ 'multipart/mixed', { 'boundary': 'NEBIKbUAj980jV2K' } ]
        // 'application/x-stuff; title*1*=us-ascii'en'This%20is%20even%20more%20; title*2*=%2A%2A%2Afun%2A%2A%2A%20; title*3="isn't it!"' returns ['application/x-stuff', { 'title': "This is even more ***fun*** isn't it!" }

        const l = this.value.length;
        var i = this.value.indexOf(';');
        if (i === -1) {
            return [this.value, {}];
        }
        var main = this.value.substr(0, i);  // the main value
        var attrs = {};  // the extra ';' separated attributes
        for (i++; i < l; i++) {
            var j = this.value.indexOf('=', i + 1);
            if (j === -1) {
                console.error('Malformed header ' + this.name + ', missing "=" after ";"');
                break;
            }
            var attrname = this.value.substring(i, j);
            attrname = attrname.replace(/^ +/, '').replace(/ +/g, '').toLowerCase();  // XXX
            var attrvalue = '';
            var inquote = false;
            for (j++; j < l; j++) {
                const c = this.value.charAt(j);
                if (c === '"') {
                    inquote = !inquote;
                    continue;
                }
                if (inquote) {
                    // We are inside double quotes
                    if (c === '\\')
                        attrvalue += this.value.charAt(++j);
                    else
                        attrvalue += c;
                } else {
                    // We are not insode double quotes
                    if (c === ';')
                        break;
                    attrvalue += c;
                }

                attrs[attrname] = attrvalue;
            }
            i = j + 1;
        }

        // Reassemble RFC2231 multiline encoded attributes
        var cleanedAttrs = {};
        for (attrname in attrs) {
            attrvalue = attrs[attrname];
            let found;
            if (found = attrname.match(/^(.*\*)([0-9])\*$/)) {
                attrname = found[1];
                if (!cleanedAttrs.hasOwnProperty(attrname))
                    cleanedAttrs[attrname] = '';
                cleanedAttrs[attrname] += attrvalue;
            } else {
                cleanedAttrs[attrname] = attrvalue;
            }
        }
        attrs = cleanedAttrs;

        // Decode the RFC2231 encoded attributes
        for (attrname in attrs) {
            let found;
            if (found = attrname.match(/^(.*)\*$/)) {
                attrvalue = attrs[attrname];
                attrname = found[1];  // drop the '*'
                attrs[attrname] = MiMsgHeader.attributeDecodeRFC2231(attrvalue);
            }
        }
        return [main, attrs];
    }

    /*
    static test() {
        const test = new MiMsgHeader('test', '');
        var tmp;
        test.value = 'multipart/mixed; boundary="nebikbuaj980jv2k"';
        tmp = test.contentSplit();
        test.value = 'multipart/mixed; boundary=';
        tmp = test.contentSplit();
        test.value = 'multipart/mixed; boundary="';
        tmp = test.contentSplit();
        test.value = 'multipart/mixed; boundary="nebikbuaj980jv2k";';
        tmp = test.contentSplit();
        test.value = 'attachment; filename="test = \\\\A\\"1234567890';
        tmp = test.contentSplit();
        test.value = 'attachment; filename="test = \\\\A\\"1234567890"; echo=1';
        tmp = test.contentSplit();
        //msg.setHeader('test', '=?ISO-8859-1?B?SWYgeW91IGNhbiByZWFkIHRoaXMgeW8=?=\r\n =?ISO-8859-2?B?dSB1bmRlcnN0YW5kIHRoZSBleGFtcGxlLg==?=');
    }
    */

    /*
     * Returns the name with nice cases.
     *
     * Change the first character of every word to upper case.
     */
    nameCaseFormated() {
        if (this.name === 'mime-version')
            return 'MIME-Version';
        // Every character at the begining or after '-'
        return this.name.replace(/(^|-)./g, c => c.toUpperCase());
    }


    /**
     * Returns the value and its attributes in a format compatible with RFC822.
     * Brutally base64 encode the whole value if it can't be sent as is.
     */
    valueWithAttrRfc822() {
        let result;
        // Quick and ugly
        let useUtf = !isString7bit(this.value);

        if (!useUtf) {
            // Some special character needs to be encoded anyway
            if (this.value.match('[?]'))
                useUtf = true;
        }

        if (useUtf) {
            let u8arr = textEncode(this.value);
            let b64 = uint8ArrayToBase64(u8arr);
            result = '=?UTF-8?B?' + b64 + '?=';
        } else {
            result = this.value;
        }

        for (let name in this.attrs) {
            let value = this.attrs[name];
            result += ';';
            if (isString7bit(value)) {
                let mustQuote = false;
                let illegalTokenChars = '()<>@,;:\\"/[]?=';
                for (let i = 0, l = value.length; i < l; i++) {
                    if (value.charCodeAt(i) <= 32 || illegalTokenChars.includes(value.charAt(i))) {
                        mustQuote = true;
                        break;
                    }
                }
                if (mustQuote)
                    value = '"' + value.replace(/\\/g, '\\\\').replace(/"/g, '\\"') + '"';
                result += name + '=' + value;
            } else {
                // RFC2231, with no language set
                result += name + '*=' + MiMsgHeader.attributeEncodeRFC2231(value);
            }
        }
        return result;
    }

    /**
     * Returns the value and attributes in a printable format
     */
    valueWithAttr() {
        var result = this.value;
        for (var attrname in this.attrs) {
            result += '; ' + attrname + '="' + this.attrs[attrname].replace(/\\/g, '\\\\').replace(/"/g, '\\"') + '"';
        }
        return result;
    }

    toRfc822Lines() {
        return this.nameCaseFormated() + ': ' + this.valueWithAttrRfc822();
    }
}


/** Message Part.
 *
 * @class
 */
export class MiMsgPart {

    constructor() {
        // headers: array of MiMsgHeader
        // Multiple header with the same name - like 'received' - are allowed
        this.headers = [];

        // body can be:
        // a string (for text/ messages)
        // a Uint8Array (for most attachments)
        // an array of MiMsgPart (for multipart/ messages)
        // a MiMsgPart (for message/rfc822)
        this.body = null;
    }

    /**
     * Returns the first header with that name.
     *
     * @param {string} - Lower case name of the header
     * @returns {MiMsgHeader} The header or null
     */
    getHeader(name) {
        for (var header of this.headers) {
            if (header.name === name)
                return header;
        }
        return null;
    }


    /**
     * Add a new header. Only usefull for Received and a few others, when multiple entries are allowed.
     * One should generally use setHeader.
     *
     * @param {string}            - Lower case name of the header
     * @param {string}            - The parsed value, decoded
     * @param {object} [attrs={}] - The extra content- attributes
     * @return {MiMsgHeader}
     */
    addHeader(name, value, attrs={}) {
        const header = new MiMsgHeader(name, value, attrs);
        this.headers.push(header);
        return header;
    }


    /**
     * Add a new header, changing previous value if it already exists.
     * See addHeader if you need duplicate entries.
     *
     * @param {string}            - Lower case name of the header
     * @param {string}            - The parsed value, decoded
     * @param {object} [attrs={}] - The extra content- attributes
     * @return {MiMsgHeader}
     */
    setHeader(name, value, attrs={}) {
        var header = this.getHeader(name);
        if (header) {
            header.value = value;
            header.attrs = attrs;
        } else {
            header = this.addHeader(name, value, attrs);
        }
        return header;
    }

    /**
     * Returns the value of a header (first one if there are several by the same name).
     * If not found, returns def.
     *
     * @param {string}             - Lower case name of the header
     * @param {string} [def=null]  - Default value
     * @return {string} The value if the header exists, def otherwise
     */
    getHeaderValue(name, def=null) {
        var header = this.getHeader(name);
        if (header)
            return header.value;
        else
            return def;
    }


    getContentTypeHeader() {
        var header = this.getHeader('content-type');
        if (!header) {
            console.error('Message has no Content-Type.');
            // RFC2045 5.2 : defaults to text/plain; charset=us-ascii :
            header = new MiMsgHeader('content-type', 'text/plain', {'charset': 'us-ascii'});
        }
        return header;
    }


    /**
     * Returns the Content-Transfer-Encoding header value
     * default value is defined by RFC1341 5.
     */
    getContentTransfertEncoding() {
        const val = this.getHeaderValue('content-transfer-encoding', '7bit');
        return val.toLowerCase();
    }


    /**
     * Used to know whether the message part show be displayed 'inline' or as an 'attachment'
     * See RFC2183
     */
    getContentDisposition() {
        const val = this.getHeaderValue('content-disposition', 'inline');
        return val.toLowerCase();
    }


    /**
     * Sets Content-Type to text/plain and initialize the body.
     * Text will be output has 7bit if possible, utf-8 quoted-printable otherwise.
     */
    setTextBody(text) {

        text = normalizeCRLF(text);

        // Encode the message using quoted-printable Content-Transfer-Encoding according to RFC1521:

        const bodyUint8arr = textEncode(text);

        var body = '';  // quoted-printable body
        var is7bits = true;
        const l = bodyUint8arr.length;
        for (var i = 0, x, linelen = 0, xenc; i < l; i++) {
            x = bodyUint8arr[i];
            if (x < 32 || x >= 128) {
                if (x === 13 && bodyUint8arr[i + 1] === 10) {
                    // Regular \r\n: Don't encode it
                    body += '\r\n';
                    i += 1; // Skip next input \n
                    linelen = 0;
                    continue;  // skip line len overflow
                }
                if (x === 9)  // \t
                    xenc = '\t';
                else {
                    is7bits = false;
                    if (x < 16)
                        xenc = '=0' + x.toString(16).toUpperCase();
                    else
                        xenc = '=' + x.toString(16).toUpperCase();
                }
            }
            else {
                if (x === 61) {  // '='
                    xenc = '=3D';
                } else {
                    if (x >= 128)
                        is7bits = false;
                    xenc = String.fromCharCode(x);
                }
            }

            if (linelen + xenc.length >= 76) {
                // We're going to be over 76 char
                body += '=\r\n';
                linelen = 0;
            }
            body += xenc;
            linelen += xenc.length;
        }

        // Check whether 7bit encoding is possible after all
        var choose7bits = false;
        if (is7bits) {
            // There was no special character
            choose7bits = true;
            for (var line of text.split('\r\n')) {
                if (line.length > rfc5322_max_line_length) {
                    choose7bits = false;
                    break;
                }
            }
        }

        if (choose7bits) {
            this.setHeader('content-type', 'text/plain', {'charset': 'us-ascii'});
            this.setHeader('content-transfer-encoding', '7bit');  // RFC1521
            this.body = text;  // Original text (with \r\n normalization)
        } else {
            this.setHeader('content-type', 'text/plain', {'charset': 'utf-8'});
            this.setHeader('content-transfer-encoding', 'quoted-printable');
            this.body = body;
        }
    }


    /*
     * @param {File} file
     * @param {String} [disposition='attachment'] - 'attachment' or 'inline'
     * @return {MiMsgPart}
     */
    static newAttachementFromFile(file, contentDisposition='attachment') {
        var attachementMessagePart = new MiMsgPart();
        attachementMessagePart.setHeader('content-disposition', contentDisposition, {'filename': file.name});
        attachementMessagePart.setHeader('content-transfer-encoding', 'base64');
        if (file.type)
            attachementMessagePart.setHeader('content-type', file.type, {'name': file.name}); // TODO required?
        attachementMessagePart.body = '';
        var b64 = file['content'];
        b64 = b64.substr(b64.indexOf(',') + 1);  // Skip everything before ','
        // Cut in lines of 76 characters
        while (b64) {
            attachementMessagePart.body += b64.substr(0, 76) + '\r\n';
            b64 = b64.substr(76);
        }
        return attachementMessagePart;
    }


    switchToMultiPart(subType='mixed') {
        const oldContentTypeHeader = this.getHeader('content-type');
        const oldContentType = oldContentTypeHeader.value;
        if (oldContentType.startsWith('multipart/')) {
            console.error('switchToMultiPart() called, but already multipart!');
            return;
        }

        var part = new MiMsgPart();

        // Move all content- headers to the part:
        for (var i = 0; i < this.headers.length; ) {
            let header = this.headers[i];
            if (header.name.toLowerCase().startsWith('content-')) {
                part.headers.push(header);
                this.headers.splice(i, 1);
            } else {
                i++;
            }
        }

        const boundary = 'nextPart' + randomId();
        this.setHeader('content-type', 'multipart/' + subType, {'boundary': boundary});

        part.body = this.body;
        this.body = [part];
    }


    addAttachement(attachementMessagePart) {
        if (this.getHeader('content-type').value.toLowerCase() != 'multipart/mixed')
            this.switchToMultiPart();

        this.body.push(attachementMessagePart);
    }


    /**
     * Output the message in a format suitable for SMTP transfert (without DATA /^./ line handling)
     */
    toRfc822Lines() {
        const contentTypeHeader = this.getHeader('content-type');
        const contentTransfertEncoding = this.getContentTransfertEncoding();
        const contentDisposition = this.getContentDisposition();

        var result = '';
        // Output the headers first
        for (var header of this.headers) {
            result += header.toRfc822Lines() + '\r\n';
        }
        result += '\r\n';

        if (typeof(this.body) === 'string') {
            result += this.body;
        } else if (Array.isArray(this.body)) {
            if (!contentTypeHeader.value.toLowerCase().startsWith('multipart/')) {
                console.error('Unsupported body type Array for Content-Type:' + contentTypeHeader.value.toLowerCase());
                result += 'Unsupported body type Array for Content-Type:' + contentTypeHeader.value.toLowerCase();
            } else {
                const boundary = contentTypeHeader.attrs['boundary'];
                if (!boundary) {
                    // rfc1341 7.2 boundary is required
                    result += 'Missing boundary of Content-Type:' + contentTypeHeader.value.toLowerCase();
                } else {
                    result += 'This is a multi-part message in MIME format.\r\n';
                    result += '\r\n';
                    for (var part of this.body) {
                        result += '\r\n--' + boundary + '\r\n';
                        result += part.toRfc822Lines();
                    }
                    result += '\r\n--' + boundary + '--\r\n';
                }
            }
        } else {
            console.error('Unsupported body type ' + typeof(this.body));
            result += 'Unsupported body type ' + typeof(this.body);
        }
        return result;
    }


    /**
     * Returns this.body as an Uint8Array
     */
    bodyAsBinary() {
        switch (this.getContentTransfertEncoding()) {
        case '7bit':
            if (typeof(this.body) === 'string') {
                return textEncode(this.body);
            }
            if (this.body instanceof Uint8Array) {
                return this.body;
            }
            break;
        case '8bit':
        case 'binary':
            return this.body;
        case 'base64':
            let b64txt = textDecode(this.body);  // base64 is utf-8 compatible
            return base64ToUint8Array(b64txt);
        case 'quoted-printable':
            let qptext;
            if (typeof(this.body) === 'string') {
                qptext = this.body;
            } else if (this.body instanceof Uint8Array) {
                qptext = textDecode(this.body);  // quoted-printable is utf-8 compatible
            } else {
                break;
            }
            return quotedPrintableDecode(qptext);
        }
        console.error('Unsupported Content-Transfert-Encoding / typeof(this.body)');
        return new Uint8Array();
    }


    /**
     * Returns this.body as a base64 compact string (no spaces)
     */
    bodyAsBase64() {
        if (this.getContentTransfertEncoding() === 'base64') {  // avoid b64->bin->b64 conversions
           let b64txt;
            if (typeof(this.body) === 'string') {
                b64txt = this.body;
            } else if (this.body instanceof Uint8Array) {
                b64txt = textDecode(this.body);  // base64 is utf-8 compatible
            } else {
                console.error('Unsupported Content-Transfert-Encoding / typeof(this.body)');
                return '';
            }
            b64txt = b64txt.replace(/[ \r\n\t]/g, '');
            return b64txt;
        }
        return uint8ArrayToBase64(this.bodyAsBinary());
    }


    /**
     * Returns the headers as HTML
     */
    headersToHtml() {
        const wantedHeaders = ['from', 'to', 'cc', 'bcc', 'date'];

        var html = '';
        html += '<div class="msg-headers">';

        let subject = this.getHeaderValue('subject', 'No subject');
        html += '<div>' + htmlEscape(subject) + '</div>';

        html += '<table class=outer><tbody><tr><td width="100%">';
        html += '<table><tbody>';

        let from = this.getHeaderValue('from', '');
        let resentfrom = this.getHeaderValue('resent-from');
        if (resentfrom)
            from += ` (resent from: ${resentfrom})`
        let organization = this.getHeaderValue('organization');
        if (organization)
            from += ` (${organization})`;
        if (from)
            html += `<tr><th>From:<td>${htmlEscape(from)}`;

        for (let name of ['to', 'cc', 'bcc', 'sender', 'list-id', 'date']) {
            let header = this.getHeader(name);
            if (!header)
                continue;
            html += '<tr>';
            html += '<th>' + htmlEscape(header.nameCaseFormated()) + ':';
            html += '<td>' + htmlEscape(header.valueWithAttr());
        }
        html += '</table></table>';

        html += '</div>';
        return html;
    }



    /**
     * Returns the message as HTML
     */
    toHtml(showHeaders = true) {
        var html = '';

        const contentTypeHeader = this.getContentTypeHeader();
        const contentType = contentTypeHeader.value;
        const contentTransfertEncoding = this.getContentTransfertEncoding();
        const contentDisposition = this.getContentDisposition();

        if (showHeaders)
            html += this.headersToHtml();

        let displayedInline = false;
        switch (contentDisposition) {
        case 'inline':
            if (contentType === 'multipart/alternative') {
                let bestType, bestI = null;
                for (let i in this.body) {
                    let altType = this.body[i].getContentTypeHeader().value.toLowerCase();
                    if (!i  // First alternative is always better than nothing
                       || altType === 'text/plain'  // Favor plain
                       || (altType === 'text/html' && bestType !== 'text/plain')  // html is ok, unless we found plain that is better
                       ) {
                        bestI = i;
                        bestType = altType;
                    }
                }
                if (bestI === null) {
                    console.error(`Content-Type:${contentType} but there is no choice.`);
                    html += '(empty multipart/alternative)<br>';
                } else {
                    html += `<div class=alternative>${ this.body[bestI].toHtml(false) }</div>`;
                }
                displayedInline = true;
            } else if (contentType.startsWith('multipart/')) {
                html += '<div class=multipart>';
                for (var part of this.body) {
                    html += part.toHtml(false);
                }
                html += '</div>';
                displayedInline = true;
            } else if (contentType.startsWith('text/')) {
                let u8arr = this.bodyAsBinary();
                let charset = contentTypeHeader.attrs['charset'];
                let text = textDecode(u8arr, charset);
                html += htmlEscape(text).replace(/\n/g, '<br>') + '<br>';
                displayedInline = true;
            } else if (contentType.startsWith('image/')) {
                html += '<hr class=preattachment>';
                let b64txt = this.bodyAsBase64();
                html += `<img src="data:${contentType};base64,${b64txt}"><br>`;
                displayedInline = true;
            } else if (contentType === 'message/rfc822') {
                html += this.body.toHtml();  // Encapsulated message
                displayedInline = true;
            } else {
                console.error(`Unsupported Content-Type:${ htmlEscape(contentType) } for Content-Disposition:inline. Treating as attachment.`);
            }
            break;

        case 'attachment':
            break;

        default:
            console.error(`Unknown Content-Disposition:${contentDisposition}. Assuming attachment.`);
            break;
        }

        if (!displayedInline) {
            let b64txt = this.bodyAsBase64();

            const contentDispositionHeader = this.getHeader('content-disposition');
            var filename;
            if (contentDispositionHeader)
                filename = contentDispositionHeader.attrs['filename'];
            if (!filename)
                filename = 'Unknown';

            html += '<hr class=preattachment>';

            // TODO check browser compatibility
            // https://medium.com/octopus-labs-london/downloading-a-base-64-pdf-from-an-api-request-in-javascript-6b4c603515eb
            // https://stackoverflow.com/questions/33154646/data-uri-link-a-href-data-doesnt-work-in-microsoft-edge
            filename = htmlEscape(filename, /[&<"]/g);
            html += `<a href="data:${contentType};base64,${b64txt}" download="${filename}" class=attachment>${filename}</a>`;
        }

        let contentDescription = this.getHeaderValue('content-description', '');
        if (contentDescription)
            html += `<div>${contentDescription}</div>`;
        return html;
    }
}



class MultiPartMessagePart extends MiMsgPart {
/* rfc1341: Multipart/mixed -> Displayed serially, Multipart/alternative -> Chose the best for you */
/* see also: digest, parallel */
    constructor() {
        this.subtype = null;
        this.boundary = null;
    }
}


/*
 * Helper function used in parsing
 * Takes a Uint8Array and returns a MiMsgPart where body is still not decoded: It still is a Uint8Array array
 */
function rfc822_split_headers(u8arr) {
    const CRLF = new Uint8Array([13, 10]); // \r\n
    var start = 0;
    var headers = []; // raw headers lines, unfolded, but not base64/quoted-pritable decoded
    while (true) {
        var headerline, i, firstChar;
        i = arrayIndexOfArray(u8arr, CRLF, start);
        if (i === -1) {
            // No more headers! Assume the body is empty
            console.error('Malformed RFC822 headers: \\r\\n not found before body.');
            headerline = textDecode(u8arr.slice(start));
            headers.push(headerline);
            start = u8arr.length;
            break;
        }
        headerline = textDecode(u8arr.slice(start, i));
        start = i + 2; // skip the line, inluding the \r\n

        if (headerline === '') {
            break;
        }
        firstChar = headerline.charAt(0);
        if (firstChar === ' ' || firstChar === '\t')
            // folded multiline header
            headers[headers.length - 1] += headerline;
        else
            headers.push(headerline);
    }

    var result = new MiMsgPart();

    for (var headerLine of headers) {
        var header = MiMsgHeader.parse(headerLine);
        if (header)
            result.headers.push(header);
    }
    result.body = u8arr.slice(start);
    return result;
}


/**
 * Parse a Uint8Array into headers and body
 * For multipart/ messages, body is an array
 * For message/rfc822 messages, body itself is a MiMsgPart
 */
export function parse_message(u8arr) {
    var msg = rfc822_split_headers(u8arr);
    const contentTypeHeader = msg.getContentTypeHeader();
    const contentType = contentTypeHeader.value.toLowerCase();
    const contentDisposition = msg.getContentDisposition();

    if (contentType.startsWith('multipart/') && contentDisposition === 'inline') {
        const boundary = contentTypeHeader.attrs['boundary'];
        if (!boundary) {
            // RFC1341 7.2 violation
            console.error(`Message with Content-Type:${contentType}, but no boundary.`);
            msg.body = `Message with Content-Type:${contentType}', but no boundary.`;
        } else {
            u8arr = msg.body;  // now working within the body
            msg.body = [];
            const uint8boundary = textEncode('--' + boundary);
            let i = 0, j;
            var prolog = null, epilog = null;
            let closedMarker = false;
            while (true) {  // while there are parts
                // First search suitable boundary is not found: At a begining of a line and followed by either '\r\n' or '--'
                // j will point at such a marker
                // additionnally, closedMarker will be true if this is an end marker
                {
                    let k = i;
                    while (true) { // while suitable boundary is not found, that is boundary followed by either '\r\n' or '--'
                        let c1, c2;
                        j = arrayIndexOfArray(u8arr, uint8boundary, k);
                        if (j === -1) {
                            console.error(`Parsing Content-Type:${contentType}, boundary=${boundary}, missing boundary end in body.`);
                            break;
                        }
                        if (j > 1 && (u8arr[j - 2] != 13 || u8arr[j - 1] != 10)) {
                            console.error(`Found boundary --${boundary} in a middle of a line.`);
                            k = j + 2;
                            continue;
                        }

                        c1 = u8arr[j + uint8boundary.length];
                        c2 = u8arr[j + uint8boundary.length + 1];
                        if (c1 === 13 && c2 === 10) {  // CRLF
                            // Good, we found a boundary
                            break;
                        } else if (c1 === 45 && c2 === 45) {  // --
                            // Good, we found the boundary end marker
                            closedMarker = true;
                            break;
                        } else {
                            console.error(`Parsing Content-Type=${contentType}, boundary=${boundary}, illegal characters ${c1},${c2} found after boundary.`);
                            k = j + uint8boundary.length;
                        }
                    }
                }

                let chunk;
                if (j === -1)
                    chunk = u8arr.slice(i);
                else if (j > 2)
                    chunk = u8arr.slice(i, j - 2);
                else
                    chunk = u8arr.slice(i, j);

                if (prolog === null) {
                    prolog = textDecode(chunk);
                } else {
                    msg.body.push(parse_message(chunk));
                }

                if (j != -1) {
                    i = j + uint8boundary.length + 2;
                    if (closedMarker) {
                        chunk = u8arr.slice(i);
                        epilog = textDecode(chunk);
                    }
                }

                if (closedMarker || j === -1)
                    break;
            }
        }
    } else if (contentType === 'message/rfc822'  && contentDisposition === 'inline') {
        msg.body = parse_message(msg.body)
    }  // else
       // the body stays Uint8Array
    return msg;
}


/* vim: set et ts=4 ft=javascript: */
