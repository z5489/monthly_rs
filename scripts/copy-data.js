import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

const srcDir = path.join(__dirname, '../data');
const destDir = path.join(__dirname, '../frontend/dist/data');

if (fs.existsSync(srcDir)) {
    fs.mkdirSync(destDir, { recursive: true });
    const files = fs.readdirSync(srcDir);
    let count = 0;
    for (const file of files) {
        if (file.endsWith('.json') || file.endsWith('.csv')) {
            fs.copyFileSync(path.join(srcDir, file), path.join(destDir, file));
            count++;
        }
    }
    console.log(`Successfully copied ${count} JSON/CSV files from data/ to frontend/dist/data/`);
} else {
    console.warn('Source data/ directory not found.');
}
