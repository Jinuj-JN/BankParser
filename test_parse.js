
const parseMoney = (str) => {
    if (typeof str !== 'string' && typeof str !== 'number') return 0;
    let clean = str.toString().trim();
    if (!clean) return 0;

    // Handle parentheses: (1,234.56) -> -1,234.56
    let isNegative = false;
    if (clean.startsWith('(') && clean.endsWith(')')) {
        isNegative = true;
        clean = clean.substring(1, clean.length - 1);
    }

    // Check for leading or trailing minus sign before stripping characters
    if (clean.startsWith('-') || clean.endsWith('-') || clean.includes('CR')) {
        isNegative = true;
    }

    // Remove currency symbols, quotes, and normalize spaces
    clean = clean.replace(/[$\s"']/g, '');

    // Remove any remaining signs now that we've captured the negativity
    clean = clean.replace(/[-+]/g, '');

    // Handle European/International format detection
    const lastComma = clean.lastIndexOf(',');
    const lastDot = clean.lastIndexOf('.');

    if (lastComma > -1 && lastComma > lastDot) {
        if (lastComma === clean.length - 3 || lastComma === clean.length - 2) {
            clean = clean.replace(/\./g, '').replace(',', '.');
        } else {
            clean = clean.replace(/,/g, '');
        }
    } else {
        clean = clean.replace(/,/g, '');
    }

    let result = parseFloat(clean);
    if (isNaN(result)) return 0;
    return isNegative ? -Math.abs(result) : result;
};

const tests = [
    ["$1,234.56", 1234.56],
    ["-$1,234.56", -1234.56],
    ["$1,234.56-", -1234.56],
    ["($1,234.56)", -1234.56],
    ["-$ 1,234.56", -1234.56],
    ["1,234.56 -", -1234.56],
    ["123.45 CR", -123.45],
    [-50.25, -50.25],
    ["-50.25", -50.25]
];

tests.forEach(([input, expected]) => {
    const result = parseMoney(input);
    console.log(`Input: ${input.toString().padEnd(15)} | Expected: ${expected.toString().padEnd(10)} | Result: ${result.toString().padEnd(10)} | ${result === expected ? 'PASS' : 'FAIL'}`);
});
