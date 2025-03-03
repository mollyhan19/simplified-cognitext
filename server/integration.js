import { spawn } from 'child_process';
import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';

// Set up __dirname equivalent for ES modules
const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const pythonPath = path.join(__dirname, '..', 'python');

/**
 * Process a Wikipedia article and generate concept maps
 * @param {string} url - Wikipedia article URL
 * @param {string} processingMode - 'section' or 'paragraph'
 * @param {string} mapType - 'hierarchical', 'network', or 'cyclic'
 * @param {string} rootConcept - Optional root concept for hierarchical maps
 * @returns {Promise<Object>} - Processing results
 */

export async function processWikipediaArticle(url, processingMode = 'section', mapType = 'hierarchical', rootConcept = null) {
    return new Promise((resolve, reject) => {
        // Command line arguments for the Python script
        const args = [
            path.join(pythonPath, 'process_wiki.py'),
            url,
            '--mode', processingMode,
            '--map-type', mapType
        ];

        // Add root concept if provided
        if (rootConcept) {
            args.push('--root');
            args.push(rootConcept);
        }

        console.log(`Executing Python script: python ${args.join(' ')}`);

        // Spawn Python process
        const pythonProcess = spawn('python', args);

        let stdoutData = '';
        let stderrData = '';

        // Capture output
        pythonProcess.stdout.on('data', (data) => {
            stdoutData += data.toString();
            console.log(`Python stdout: ${data}`);
        });

        pythonProcess.stderr.on('data', (data) => {
            stderrData += data.toString();
            console.error(`Python stderr: ${data}`);
        });

        // Handle process completion
        pythonProcess.on('close', (code) => {
            console.log(`Python process exited with code ${code}`);

            if (code !== 0) {
                return reject({
                    error: 'Python script execution failed',
                    stdout: stdoutData,
                    stderr: stderrData
                });
            }

            // Try to parse the results from stdout
            try {
                // Look for JSON output in the stdout
                const jsonMatch = stdoutData.match(/\{[\s\S]*\}/);
                if (jsonMatch) {
                    const results = JSON.parse(jsonMatch[0]);
                    return resolve(results);
                }

                // If no JSON found, parse structured output manually
                const results = parseProcessOutput(stdoutData);
                return resolve(results);
            } catch (error) {
                console.error('Error parsing Python output:', error);
                return reject({
                    error: 'Failed to parse Python output',
                    stdout: stdoutData,
                    stderr: stderrData
                });
            }
        });
    });
}

/**
 * Parse structured output from the Python script
 * @param {string} output - Script output
 * @returns {Object} - Parsed results
 */
function parseProcessOutput(output) {
    const results = {
        title: '',
        category: '',
        total_entities: 0,
        total_relations: 0,
        entity_file: '',
        relation_file: '',
        map_file: '',
        map_type: '',
        timestamp: ''
    };

    // Extract key information from the output using regex
    const titleMatch = output.match(/Title: (.+)/);
    if (titleMatch) results.title = titleMatch[1];

    const categoryMatch = output.match(/Category: (.+)/);
    if (categoryMatch) results.category = categoryMatch[1];

    const entitiesMatch = output.match(/Entities extracted: (\d+)/);
    if (entitiesMatch) results.total_entities = parseInt(entitiesMatch[1]);

    const relationsMatch = output.match(/Relations extracted: (\d+)/);
    if (relationsMatch) results.total_relations = parseInt(relationsMatch[1]);

    const mapTypeMatch = output.match(/Map type: (.+)/);
    if (mapTypeMatch) results.map_type = mapTypeMatch[1];

    const entityFileMatch = output.match(/Entity file: (.+)/);
    if (entityFileMatch) results.entity_file = entityFileMatch[1];

    const relationFileMatch = output.match(/Relation file: (.+)/);
    if (relationFileMatch) results.relation_file = relationFileMatch[1];

    const mapFileMatch = output.match(/Map file: (.+)/);
    if (mapFileMatch) results.map_file = mapFileMatch[1];

    return results;
}

/**
 * Copy the generated map file to the public directory for web access
 * @param {string} mapFile - Path to the generated map file
 * @param {string} publicDir - Public directory path
 * @returns {string} - Public URL path to the map file
 */
export function prepareMapForWeb(mapFile, publicDir) {
    if (!mapFile || !fs.existsSync(mapFile)) {
        throw new Error('Map file not found');
    }

    // Create a copy in the public directory
    const fileName = path.basename(mapFile);
    const publicPath = path.join('generated', fileName);
    const destPath = path.join(publicDir, publicPath);

    // Create generated directory if it doesn't exist
    const genDir = path.join(publicDir, 'generated');
    if (!fs.existsSync(genDir)) {
        fs.mkdirSync(genDir, { recursive: true });
    }

    // Copy the file
    fs.copyFileSync(mapFile, destPath);

    return publicPath;
}