// ES Module syntax
import express from 'express';
import cors from 'cors';
import path from 'path';
import { fileURLToPath } from 'url';
import dotenv from 'dotenv';
import fetch from 'node-fetch';
import { spawn } from 'child_process';
import fs from 'fs';

// Load environment variables from .env file
dotenv.config();

// Set up __dirname equivalent for ES modules
const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

// Create Express app
const app = express();
const PORT = process.env.PORT || 3000;

// Enable middleware
app.use(cors());
app.use(express.json({ limit: '10mb' }));
app.use(express.static(path.join(__dirname, 'public')));

// Ensure output directories exist
const generatedDir = path.join(__dirname, 'public', 'generated');
if (!fs.existsSync(generatedDir)) {
  fs.mkdirSync(generatedDir, { recursive: true });
}

const pythonOutputDir = path.join(__dirname, 'python', 'output');
if (!fs.existsSync(pythonOutputDir)) {
  fs.mkdirSync(pythonOutputDir, { recursive: true });
}

// New endpoint to process Wikipedia articles directly
app.post('/api/process-wiki', async (req, res) => {
  try {
    const { url, processingMode, mapType, rootConcept } = req.body;

    if (!url) {
      return res.status(400).json({ error: 'URL is required' });
    }

    console.log(`Processing Wikipedia article: ${url}`);
    console.log(`Mode: ${processingMode || 'section'}, Map Type: ${mapType || 'hierarchical'}`);

    // Command line arguments for the Python script
    const args = [
      path.join(__dirname, 'python', 'process_wiki.py'),
      url
    ];

    // Add optional arguments if provided
    if (processingMode) {
      args.push('--mode', processingMode);
    }

    if (mapType) {
      args.push('--map-type', mapType);
    }

    if (rootConcept) {
      args.push('--root', rootConcept);
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
        return res.status(500).json({
          error: 'Python script execution failed',
          stdout: stdoutData,
          stderr: stderrData
        });
      }

      // Try to parse the results from stdout
      try {
        // Look for the results section in the output
        const resultsMatch = stdoutData.match(/Processing complete!\n([\s\S]*)/);
        if (resultsMatch) {
          const resultsText = resultsMatch[1];

          // Parse key information
          const results = {
            title: (resultsText.match(/Title: (.+)/) || [])[1] || '',
            category: (resultsText.match(/Category: (.+)/) || [])[1] || '',
            total_entities: parseInt((resultsText.match(/Entities extracted: (\d+)/) || [])[1] || '0'),
            total_relations: parseInt((resultsText.match(/Relations extracted: (\d+)/) || [])[1] || '0'),
            map_type: (resultsText.match(/Map type: (.+)/) || [])[1] || '',
            entity_file: (resultsText.match(/Entity file: (.+)/) || [])[1] || '',
            relation_file: (resultsText.match(/Relation file: (.+)/) || [])[1] || '',
            map_file: (resultsText.match(/Map file: (.+)/) || [])[1] || ''
          };

          // Check if map file exists and copy to public directory if needed
          if (results.map_file && fs.existsSync(results.map_file)) {
            const fileName = path.basename(results.map_file);
            const publicPath = path.join('generated', fileName);
            const destPath = path.join(__dirname, 'public', publicPath);

            // Copy file to public directory
            fs.copyFileSync(results.map_file, destPath);

            // Add public path to results
            results.map_public_path = '/' + publicPath.replace(/\\/g, '/');
          }

          return res.json({
            success: true,
            results
          });
        } else {
          return res.status(500).json({
            error: 'Could not parse Python script output',
            stdout: stdoutData,
            stderr: stderrData
          });
        }
      } catch (error) {
        console.error('Error parsing Python output:', error);
        return res.status(500).json({
          error: 'Failed to parse Python output',
          details: error.message,
          stdout: stdoutData,
          stderr: stderrData
        });
      }
    });
  } catch (error) {
    console.error('Error processing Wikipedia article:', error);
    res.status(500).json({
      error: 'Failed to process Wikipedia article',
      details: error.message
    });
  }
});

// Endpoint to proxy OpenAI API requests
app.post('/api/generate-constellations', async (req, res) => {
  try {
    const apiKey = process.env.OPENAI_API_KEY;

    if (!apiKey) {
      return res.status(500).json({
        error: 'API key not configured on server. Please add it to your .env file.'
      });
    }

    const { prompt } = req.body;

    console.log('Processing request with LLM...');

    // Make request to OpenAI
    const response = await fetch('https://api.openai.com/v1/chat/completions', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${apiKey}`
      },
      body: JSON.stringify({
        model: 'gpt-4o-mini',
        messages: [
          {
            role: 'system',
            content: 'You are a helpful assistant specialized in analyzing concept maps and knowledge graphs.'
          },
          {
            role: 'user',
            content: prompt
          }
        ],
        temperature: 0.1,
        max_tokens: 2000
      })
    });

    if (!response.ok) {
      const errorData = await response.json();
      console.error('OpenAI API error:', errorData);
      return res.status(response.status).json({
        error: `OpenAI API error: ${errorData.error?.message || 'Unknown error'}`
      });
    }

    const data = await response.json();
    console.log('LLM processing complete');

    res.json(data);
  } catch (error) {
    console.error('Server error:', error);
    res.status(500).json({ error: `Server error: ${error.message}` });
  }
});

// Endpoint to generate hierarchical map using Python
app.post('/api/generate-hierarchical', async (req, res) => {
  try {
    const { data, rootConcept } = req.body;

    if (!data) {
      return res.status(400).json({ error: 'No data provided' });
    }

    // Create a unique filename for this request
    const timestamp = Date.now();
    const inputFilename = `input_${timestamp}.json`;
    const outputFilename = `hierarchical_${timestamp}.html`;

    // Write the input JSON to a file
    const inputPath = path.join(__dirname, 'python', inputFilename);
    fs.writeFileSync(inputPath, JSON.stringify(data, null, 2));

    // Set up the output path
    const outputPath = path.join(pythonOutputDir, outputFilename);
    const publicOutputPath = path.join('generated', outputFilename);

    // Command line arguments for the Python script
    const args = [
      path.join(__dirname, 'python', 'hierarchical_generator.py'),
      inputPath,
      outputPath
    ];

    // Add root concept if provided
    if (rootConcept) {
      args.push('--root');
      args.push(rootConcept);
    }

    console.log(`Executing Python script: python ${args.join(' ')}`);

    // Use processWikipediaArticle from integration module
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

      // Clean up the input file
      try {
        fs.unlinkSync(inputPath);
      } catch (err) {
        console.error(`Error deleting input file: ${err.message}`);
      }

      if (code !== 0) {
        return res.status(500).json({
          error: 'Python script execution failed',
          stdout: stdoutData,
          stderr: stderrData
        });
      }

      // Check if output file exists
      if (!fs.existsSync(outputPath)) {
        return res.status(500).json({
          error: 'Python script did not generate output file'
        });
      }

      // Copy the output file to the public directory
      fs.copyFileSync(
        outputPath,
        path.join(__dirname, 'public', publicOutputPath)
      );

      // Return the path to the generated file
      res.json({
        success: true,
        filePath: publicOutputPath
      });
    });
  } catch (error) {
    console.error('Hierarchical map generation error:', error);
    res.status(500).json({ error: `Server error: ${error.message}` });
  }
});

// Endpoint to handle file parsing directly on the server
app.post('/api/parse-json', express.text({ limit: '10mb' }), (req, res) => {
  try {
    // Parse the JSON content
    const parsedData = JSON.parse(req.body);
    res.json(parsedData);
  } catch (error) {
    res.status(400).json({ error: `Invalid JSON: ${error.message}` });
  }
});

// Endpoint for concept explanations
app.post('/api/generate-explanation', async (req, res) => {
  try {
    const apiKey = process.env.OPENAI_API_KEY;

    if (!apiKey) {
      return res.status(500).json({
        error: 'API key not configured on server. Please add it to your .env file.'
      });
    }

    const { prompt } = req.body;

    console.log('Generating concept explanation...');

    // Make request to OpenAI
    const response = await fetch('https://api.openai.com/v1/chat/completions', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${apiKey}`
      },
      body: JSON.stringify({
        model: 'gpt-4o-mini', // Use a faster model for explanations
        messages: [
          {
            role: 'system',
            content: 'You are a helpful assistant that provides concise, accurate explanations of concepts.'
          },
          {
            role: 'user',
            content: prompt
          }
        ],
        temperature: 0.2,
        max_tokens: 100
      })
    });

    if (!response.ok) {
      const errorData = await response.json();
      console.error('OpenAI API error:', errorData);
      return res.status(response.status).json({
        error: `OpenAI API error: ${errorData.error?.message || 'Unknown error'}`
      });
    }

    const data = await response.json();

    // Send back just the explanation text
    res.json({ explanation: data.choices[0].message.content });
  } catch (error) {
    console.error('Server error:', error);
    res.status(500).json({ error: `Server error: ${error.message}` });
  }
});

app.get('/api/get-api-key', (req, res) => {
    const apiKey = process.env.OPENAI_API_KEY;

    if (!apiKey) {
        return res.status(500).json({
            error: 'API key not configured on server. Please add it to your .env file.'
        });
    }

    // Only send a partial key for security
    res.json({
        apiKey: apiKey ? apiKey.substring(0, 5) + '...' : null
    });
});

// Serve the main HTML file for all other routes
app.get('*', (req, res) => {
  res.sendFile(path.join(__dirname, 'public', 'index.html'));
});

// Start the server
app.listen(PORT, () => {
  console.log(`Server running at http://localhost:${PORT}`);
  console.log(`Make sure you've added your OpenAI API key to the .env file!`);
});