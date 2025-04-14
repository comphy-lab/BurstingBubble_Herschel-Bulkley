/**
# Independent Viewer for Basilisk Simulation Output

This tool provides a visualization-only interface for Basilisk simulation output.
Key features:
- Monitors a restart file for changes and updates the display automatically
- Completely independent from simulation (doesn't control or pause it)
- Displays visualization in a browser window via WebSockets

Typical usage:
~~~bash
independent_viewer /path/to/file/restart
~~~

Options:
- `-interval N`: Check for file changes every N seconds (default: 2)
- `-debug`: Enable verbose debug output
*/

#define DISPLAY 0          // Run immediately, no play controls
#define DISPLAY_NO_CONTROLS // Don't show any controls
#include "display.h"

// Global tracking variables
static char g_filepath[1024] = "";
static double g_file_size = -1;
static double g_last_check_time = 0;
static double g_last_reload_time = 0;
static int g_refresh_interval = 2;
static bool g_debug = false;

// Function to check if file has changed
bool file_has_changed(const char *path) {
  FILE *fp = fopen(path, "r");
  if (!fp) {
    if (g_debug)
      fprintf(stderr, "Cannot open file: %s\n", path);
    return false;
  }
  
  // Get file size
  fseek(fp, 0L, SEEK_END);
  double size = ftell(fp);
  fclose(fp);
  
  // First time check
  if (g_file_size < 0) {
    g_file_size = size;
    strcpy(g_filepath, path);
    if (g_debug)
      fprintf(stderr, "Initial file size: %.0f bytes\n", size);
    return false;
  }
  
  // If size changed, file has changed
  if (size != g_file_size) {
    if (g_debug)
      fprintf(stderr, "File size changed: %.0f -> %.0f bytes\n", g_file_size, size);
    g_file_size = size;
    return true;
  }
  
  return false;
}

// Function to reload the file and update visualization
bool reload_file(const char *path) {
  if (g_debug)
    fprintf(stderr, "Attempting to reload file: %s\n", path);
  
  // Save current time
  g_last_reload_time = t;
  
  // Try to restore file contents
  FILE *fp = fopen(path, "r");
  if (!fp) {
    fprintf(stderr, "Error: Cannot open file for reload: %s\n", path);
    return false;
  }
  fclose(fp);
  
  // Reload the file
  if (!restore(path, list = all)) {
    fprintf(stderr, "Error: Could not restore from '%s'\n", path);
    return false;
  }
  
  // Update grid and visualization
  restriction(all);
  fields_stats();
  
  // Force full visualization update
  display("reset();");  // Reset the view
  display("clear();");  // Clear current display
  display("box();");    // Draw the box
  display_update(INT_MAX);
  
  fprintf(stderr, "Successfully reloaded file: %s at time t = %g\n", path, t);
  return true;
}

int main(int argc, char *argv[])
{
  char *file = "dump"; 
  g_refresh_interval = 2; // Default refresh interval in seconds
  
  // Process arguments
  argc--; argv++;
  for (char *arg = *argv; argc > 0; argc--, arg = *++argv) {
    if (!strcmp(arg, "-debug") || !strcmp(arg, "-d")) {
      Display.debug = true;
      g_debug = true;
    }
    else if (!strcmp(arg, "-interval") && argc > 1) {
      g_refresh_interval = atoi(argv[1]);
      argc--; argv++;
    }
    else
      file = arg;
  }
  
  // Initial load of the file
  fprintf(stderr, "Loading file: %s\n", file);
  if (!restore(file, list = all)) {
    fprintf(stderr, "Error: could not restore from '%s'\n", file);
    exit(1);
  }
  
  // Initialize file tracking
  g_file_size = -1;
  file_has_changed(file);  // Initialize tracking
  g_last_reload_time = t;
  
  restriction(all);
  fields_stats();

  // Display connection URL
  fputc('\n', stderr);
  display_url(stderr);
  fputc('\n', stderr);
  fprintf(stderr, "Monitoring file for changes every %d seconds...\n", g_refresh_interval);
  fprintf(stderr, "Press Ctrl+C to stop.\n\n");

  // Initial display
  display("box();");
  
  // Main monitoring loop
  g_last_check_time = t;
  
  while (1) {
    // Check for interface events (with shorter timeout)
    if (display_poll(100))
      display_update(INT_MAX);
      
    // Only check for file changes periodically
    if (t - g_last_check_time >= g_refresh_interval) {
      g_last_check_time = t;
      
      // Check if file has changed
      if (file_has_changed(file)) {
        // Don't reload too frequently
        if (t - g_last_reload_time >= 1.0) {
          reload_file(file);
        } else {
          if (g_debug)
            fprintf(stderr, "File changed, but waiting for reload cooldown...\n");
        }
      }
    }
    
    // Sleep a bit to reduce CPU usage
    usleep(50000); // 50ms sleep
  }
  
  display_destroy();
  return 0;
} 