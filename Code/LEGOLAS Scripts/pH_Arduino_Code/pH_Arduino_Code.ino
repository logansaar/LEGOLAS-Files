/*
 # This sample code is used to test the pH meter V1.0.
 # Editor : YouYou
 # Ver    : 1.0
 # Product: analog pH meter
 # SKU    : SEN0161
*/
#define SensorPin A0           //pH meter Analog output to Arduino Analog Input 0
// #define Offset 0.75            //deviation compensate
#define ph4Voltage 1.03       //SUERKEN - added individual define voltages so offset can be calculated in code
#define ph7Voltage 1.74
#define LED 13
#define samplingInterval 20
#define printInterval 1000
#define ArrayLenth  40    //times of collection
#define PrintValue 1     //SUERKEN - Set PrintValue to 0 to print voltage and 1 to print pHValue
int pHArray[ArrayLenth];   //Store the average value of the sensor feedback
int pHArrayIndex=0;
float slope = (7 - 4)/(ph7Voltage - ph4Voltage);  //SUERKEN - Calculating slope and offset inside code
float offset = 4 - ph4Voltage * slope;
void setup(void)
{
  pinMode(LED,OUTPUT);
  Serial.begin(9600);
     //Test the serial monitor
}
void loop(void)
{
  static unsigned long samplingTime = millis();
  static unsigned long printTime = millis();
  static float pHValue,voltage;
  if(millis()-samplingTime > samplingInterval)
  {
      pHArray[pHArrayIndex++]=analogRead(SensorPin);
      if(pHArrayIndex==ArrayLenth)pHArrayIndex=0;
      voltage = avergearray(pHArray, ArrayLenth)*5.0/1024;
      pHValue = slope*voltage+offset; //SUERKEN - Changed to lowercase offset 
      samplingTime=millis();
  }
  if(millis() - printTime > printInterval)   //Every 800 milliseconds, print a numerical, convert the state of the LED indicator
  {
    if(PrintValue == 0) { // PrintValue determines if we will print out the voltage or the pHValue.
      Serial.println(voltage,2);
      digitalWrite(LED,digitalRead(LED)^1);
      printTime=millis();
    }
    else { 
      Serial.println(pHValue,2);
      digitalWrite(LED,digitalRead(LED)^1);
      printTime=millis();
    }
  }
}
double avergearray(int* arr, int number){
  int i;
  int max,min;
  double avg;
  long amount=0;
  if(number<=0){
    Serial.println("Error number for the array to avraging!/n");
    return 0;
  }
  if(number<5){   //less than 5, calculated directly statistics
    for(i=0;i<number;i++){
      amount+=arr[i];
    }
    avg = amount/number;
    return avg;
  }else{
    if(arr[0]<arr[1]){
      min = arr[0];max=arr[1];
    }
    else{
      min=arr[1];max=arr[0];
    }
    for(i=2;i<number;i++){
      if(arr[i]<min){
        amount+=min;        //arr<min
        min=arr[i];
      }else {
        if(arr[i]>max){
          amount+=max;    //arr>max
          max=arr[i];
        }else{
          amount+=arr[i]; //min<=arr<=max
        }
      }//if
    }//for
    avg = (double)amount/(number-2);
  }//if
  return avg;
}
