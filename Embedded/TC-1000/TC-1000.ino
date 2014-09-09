#include <OneWire.h>
#include <SPI.h>
#include <Wire.h>
#include <Adafruit_GFX.h>
#include <Adafruit_SSD1306.h>
#include <EEPROM.h>

// DS18S20 Temperature chip i/o
OneWire ds(2);  // on pin 2

//Constants
const int RELAY = 3;                           //Relay pin to control heater
const int OLED_RESET = 4;                      //Pin to control OLED
const int TTEMP_ADDR = 69;                     //ROM address for target temperature
const int F_ADDR = 70;                         //ROM address for Scale storage
const int SCREEN_WIDTH = 128;                  //Width of OLED in pixels
const int CHAR_WIDTH = 7;                      //Width of text size 1 character in pixels
const int buttons[3] = {9,10,11};              //buttons pin numbers: Menu, up, down
const String MENU_ITEMS[3] = {"Set Scale", "Set Target", "Back"};    //Menu Entries

//Variables
int buttonVals[3] = {LOW,LOW,LOW};             //Button Readings 
int HighByte, LowByte, TReading, SignBit, Tc_100, Whole, Fract;    //Temperature reading helper variables
int prev = LOW;                                //Last reading of menu button
long time = 0;                                 // the last time the output pin was toggled
long debounce = 250;                           // the debounce time, increase if the output flickers
byte i;
byte present = 0;
byte data[12];
byte addr[8];                                 //Temperature reading helper variables
float targetTemp;                             //Desired Temperature
float currTemp, lastTemp;
char readTemp[8];
//Temperature reading

int mode = 0;                                   // Determines mode of operation: Menu, readout, etc.
int menuState = 0;                              // Highlighted menu item
int fahrenheit = 0;                             //0 for C, 1 for F

//PID variables
int proportional;
float integral[3] = {0,0,0};
int run_number=0;
float total, control, derivative;;

//Object for screen control
Adafruit_SSD1306 display(OLED_RESET);

//Display splash screen for startup
void splash(){
  display.clearDisplay();
  display.setTextSize(2);
  display.setTextColor(WHITE);
  display.setCursor(24,0);
  display.println("TC-1000");
  display.setTextSize(1);
  display.print("     Antares Micro");
  display.display();
}

//Print (but do not display) left menu with up/down arrows
void leftMenu(String option){
  display.setTextSize(1);
  display.setTextColor(WHITE);
  display.setCursor(0,0);
  display.print(option);
  display.fillTriangle(0,18,6,18,3,12,WHITE);
  display.fillTriangle(0,24,6,24,3,30,WHITE);
}

//Print screen for setting target temperature (deprecated)
void printSet(){
  display.clearDisplay();
  leftMenu("Set");
  display.setTextSize(2);
  display.setCursor(0,0);
  if(fahrenheit) display.println(String(int(toFahrenheit(targetTemp))) + " F");
  else display.println(String(int(targetTemp)) + " C");
  display.display();
}

//Print and Display Menu Screen
//modified 8-21 SM  //
void printMenu(){
  display.clearDisplay();
  leftMenu("Select");
  display.setCursor(0,0);
  for(int i = 0;i<3;i = i+1){
    if(i==menuState) printlnCenterInverted(MENU_ITEMS[i]); 
    else printlnCenter(MENU_ITEMS[i],WHITE);
  }
  display.display();
}
//end

//Print and Display temp readout screen
//added 8-19 SM
void printTemp(short target, float current){
  display.clearDisplay();
  display.setTextSize(1);
  display.setTextColor(WHITE);
  display.setCursor(0,0);
  display.println("Menu  Target  Current");
  display.setTextSize(2);
  display.print("   ");
  display.print(int(target));
  display.print(" ");
  printFloat(current,1);
  display.fillTriangle(0,18,6,18,3,12,WHITE);
  display.fillTriangle(0,24,6,24,3,30,WHITE);
  display.display();
}
//end

//Fill button reading array
void readButtons(){
  for(int i=0;i<3;i = i+1) buttonVals[i] = digitalRead(buttons[i]);
}

//added 8-19 SM //prints string to right side of OLED
void printRight(String string, int y){
  display.setTextSize(1);
  display.setCursor(SCREEN_WIDTH-CHAR_WIDTH*string.length(),y);
  display.print(string);
}
//end

//Print string to center of non-menu region, with line break
void printlnCenter(String string, int color){
  display.setTextSize(1);
  display.setTextColor(color);
  int x = (SCREEN_WIDTH + 7*CHAR_WIDTH - (CHAR_WIDTH*string.length()))/2;
  display.setCursor(x,display.getY());
  display.println(string);
}

//Print inverted string to center of non-menu region, with line break
void printlnCenterInverted(String string){
  display.setTextSize(1);
  display.setTextColor(BLACK,WHITE);
  int x = (SCREEN_WIDTH + 7*CHAR_WIDTH - (CHAR_WIDTH*string.length()))/2;
  display.setCursor(x,display.getY());
  display.println(string);
}

//Display scale-setting screen
//Added 8-19 SM
void printSetScale(){
  display.clearDisplay();
  leftMenu("Back");
  display.setCursor(0,12);
  if(fahrenheit) printlnCenter("Fahrenheit", WHITE);
  else printlnCenter("Celsius", WHITE);
  display.display();
}
//end

//temperature conversion functions
//added 8-19 SM

float toFahrenheit(float celsius){
  return (celsius*9.0/5.0)+32;
}

// printFloat prints out the float 'value' rounded to 'places' places after the decimal point
void printFloat(float value, int places) {
  // this is used to cast digits 
  int digit;
  float tens = 0.1;
  int tenscount = 0;
  int i;
  float tempfloat = value;

  // make sure we round properly. this could use pow from <math.h>, but doesn't seem worth the import
  // if this rounding step isn't here, the value  54.321 prints as 54.3209

  // calculate rounding term d:   0.5/pow(10,places)  
  float d = 0.5;
  if (value < 0)
    d *= -1.0;
  // divide by ten for each decimal place
  for (i = 0; i < places; i++)
    d/= 10.0;    
  // this small addition, combined with truncation will round our values properly 
  tempfloat +=  d;

  // first get value tens to be the large power of ten less than value
  // tenscount isn't necessary but it would be useful if you wanted to know after this how many chars the number will take

  if (value < 0)
    tempfloat *= -1.0;
  while ((tens * 10.0) <= tempfloat) {
    tens *= 10.0;
    tenscount += 1;
  }


  // write out the negative if needed
  if (value < 0)
    display.print('-');

  if (tenscount == 0)
    display.print(0, DEC);

  for (i=0; i< tenscount; i++) {
    digit = (int) (tempfloat/tens);
    display.print(digit, DEC);
    tempfloat = tempfloat - ((float)digit * tens);
    tens /= 10.0;
  }

  // if no places after decimal, stop now and return
  if (places <= 0)
    return;

  // otherwise, write the point and continue on
  display.print('.');  

  // now write out each decimal place by shifting digits one by one into the ones place and writing the truncated value
  for (i = 0; i < places; i++) {
    tempfloat *= 10.0; 
    digit = (int) tempfloat;
    display.print(digit,DEC);  
    // once written, subtract off that digit
    tempfloat = tempfloat - (float) digit; 
  }
}
  
///////////////////////////////////////////////////////////////////////////////////////////////////////////////////
  
void setup() {
  // initialize inputs/outputs
  // start serial port
  Serial.begin(9600);
  pinMode(RELAY, OUTPUT);
  pinMode(OLED_RESET, OUTPUT);
  for(int i=0; i<3; i++){
    pinMode(buttons[i],INPUT);
  }
  
  //intialize display
  display.begin(SSD1306_SWITCHCAPVCC, 0x3C);  // initialize with the I2C addr 0x3C (for the 128x32)
  //splash();
  //delay(100);
  //display.clearDisplay();

  //pull target from ROM, or else set default
  byte ROM = EEPROM.read(TTEMP_ADDR);
  if(ROM != 0) targetTemp = ROM;
  else targetTemp = 30;
  
  //pull scale from ROM, or else set celsius
  ROM = EEPROM.read(F_ADDR);
  if(ROM != 0) fahrenheit = 1;
  else fahrenheit = 0;
  
  Serial.print("30");
  Serial.print(" ");
  Serial.print(fahrenheit);
  Serial.print(" ");
  Serial.println(targetTemp);
  
}

///////////////////////////////////////////////////////////////////////////////////////////////////////

void loop(void) {
  
  int targetChangeFlag = 0;
  int scaleChangeFlag = 0;
    
  readButtons();
  
  //check button 1
  if (buttonVals[0] == HIGH && millis() - time > debounce) {
    
    //handle different mode cases
    switch(mode){
      case 0: //if in Temp readout
        mode = 1; //set to menu mode
        printMenu();
        break;
      case 1: //Menu
        switch(menuState){
          
          case 0: //set Scale
            mode = 3;
            printSetScale();
            break;
            
          case 1: //set Target
            mode = 2;
            printSet();
            break;
            
          case 2: //Back
            mode = 0;
            break;
        }
        time = millis();    
        break;
        
      case 2: //Set Target
        mode = 1;
        EEPROM.write(TTEMP_ADDR,targetTemp);
        printMenu();
        break;
      case 3: //Set Scale
        mode = 1;
        EEPROM.write(F_ADDR,fahrenheit);
        printMenu();
        break;
    }
    time = millis();
    
  }  
  
  //If button 1 has not been hit, handle current case
  switch(mode){
     
    //default temp readout mode
    case 0:
    
      readButtons();
      if(buttonVals[1] == HIGH && millis() - time > debounce){
        if(fahrenheit) targetTemp = targetTemp + 5.0/9.0;
        else targetTemp = targetTemp+1;
        EEPROM.write(TTEMP_ADDR,targetTemp);
        Serial.print(currTemp);
        Serial.print(" ");
        Serial.print(fahrenheit);
        Serial.print(" ");
        Serial.println(targetTemp);
        time = millis();
      }
      else if(buttonVals[2] == HIGH && millis() - time > debounce){
        if(fahrenheit) targetTemp = targetTemp - 5.0/9.0;
        else targetTemp = targetTemp-1;
        EEPROM.write(TTEMP_ADDR,targetTemp);
        Serial.print(currTemp);
        Serial.print(" ");
        Serial.print(fahrenheit);
        Serial.print(" ");
        Serial.println(targetTemp);
        time = millis();
      }
      
      if ( !ds.search(addr)) {
          ds.reset_search();
          return;
      }
      
      ds.reset();
      ds.select(addr);
      ds.write(0x44,1);         // start conversion, with parasite power on at the end
      present = ds.reset();
      ds.select(addr);    
      ds.write(0xBE);         // Read Scratchpad
      
      for ( i = 0; i < 9; i++) {           // we need 9 bytes
        data[i] = ds.read();
      }
      LowByte = data[0];
      HighByte = data[1];
      TReading = (HighByte << 8) + LowByte;
      SignBit = TReading & 0x8000;  // test most sig bit
      if (SignBit) // negative
      {
        TReading = (TReading ^ 0xffff) + 1; // 2's comp
      }
      Tc_100 = (6 * TReading) + TReading / 4;    // multiply by (100 * 0.0625) or 6.25
      
      Whole = Tc_100 / 100;  // separate off the whole and fractional portions
      Fract = Tc_100 % 100;
      
      //added 8-16
      lastTemp = currTemp;
      //end
      
      currTemp = Whole + float(Fract/100.0);
      
      if (SignBit) // If it's negative
      {
         currTemp = -currTemp;
      }
      
      //print value to OLED
      if(fahrenheit) printTemp(int(toFahrenheit(targetTemp)), toFahrenheit(currTemp));
      else printTemp(int(targetTemp),currTemp);
      
      //Turn heater on or off
      derivative = lastTemp - currTemp;
      integral[run_number % 3] = targetTemp - currTemp;
      total = 0;

      for (i=0; i<3; i++){
          total = total+integral[i];
      }
      
      proportional = targetTemp - currTemp;
      control = proportional + derivative*(1.25) + total*(.75);
      
      if (control > .01) {
          digitalWrite(RELAY, HIGH);
      }
      
      else if (control < -.01) {
         digitalWrite(RELAY, LOW);
      }
      
//      if(currTemp < (targetTemp - .05)) digitalWrite(RELAY, HIGH);
//      else digitalWrite(RELAY, LOW);

      run_number = (run_number+1)%3;
      
      break;
      
    case 1:
      
      readButtons();
      
      if(buttonVals[1] == HIGH && millis() - time > debounce){
        if(menuState>0) menuState = menuState-1;
        printMenu();
        time = millis();
        break;
      }
      else if(buttonVals[2] == HIGH && millis() - time > debounce){
        if(menuState<2) menuState = menuState+1;
        printMenu();
        time = millis();
        break;
      }
      break;
      
    case 2:
      readButtons();
      if(buttonVals[1] == HIGH && millis() - time > debounce){
        if(fahrenheit) targetTemp = targetTemp + 5.0/9.0;
        else targetTemp = targetTemp+1;
        printSet();
        time = millis();
      }
      else if(buttonVals[2] == HIGH && millis() - time > debounce){
        if(fahrenheit) targetTemp = targetTemp - 5.0/9.0;
        else targetTemp = targetTemp-1;
        printSet();
        time = millis();
      }
      break;
      
    case 3:
      readButtons();
      if(buttonVals[1] == HIGH && millis() - time > debounce){
        fahrenheit = 0;
        printSetScale();
        time = millis();
        scaleChangeFlag = 1;
      }
      else if(buttonVals[2] == HIGH && millis() - time > debounce){
        fahrenheit = 1;
        printSetScale();
        time = millis();
        scaleChangeFlag = 1;
      }
      break;
      
      //end
  }
      
 //added 8-16 //moved 8-29

  if (Serial.available() > 0) {
    Serial.readStringUntil('\n').toCharArray(readTemp,8);
    if(readTemp[0] == 'F') fahrenheit = 1;
    else if(readTemp[0] == 'C') fahrenheit = 0;
    else targetTemp = atof(readTemp);
    EEPROM.write(TTEMP_ADDR,targetTemp);
    EEPROM.write(F_ADDR,fahrenheit);
  }

  //end
  
  //modified 8-29
  //print packet of values to serial monitor for retrieval by GUI
  Serial.print(currTemp);
  Serial.print(" ");
  if(scaleChangeFlag){
    Serial.println(fahrenheit);
  }
  else {
    Serial.println();
  }
}

