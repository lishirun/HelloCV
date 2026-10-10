#include<iostream>
using namespace std; 
int main()
{
	int k,num=0,sum=0;
	cin>>k;
	int v[k],p[k];
	double h[k];
	char name[k],t;
	for(int i=0;i<k;i++)
		cin>>name[i]>>v[i]>>p[i]>>h[i];
	for(int j=0;j<k-1;j++)
	{
		if(v[j]<v[j+1])
		{
			t=name[j];
			name[j]=name[j+1];
			name[j+1]=t;
			num++;
		 }
    }
	for(int n=0;n<k-1-num;n++)
	{
		if(p[n]<=p[n+1])
		{
			t=name[n];
			name[n]=name[n+1];
			name[n+1]=t;
			sum++;
		 } 
	}
	if(k-num-sum-1<=0&&h[0]>h[1])
	{
		t=name[0];
		name[0]=name[1];
		name[1]=t;
	}
	for(int m=0;m<=k-num-sum-1;m++)
	{
		if(h[m]<h[m+1]) 
		{
			t=name[m];
			name[m]=name[m+1];
			name[m+1]=t;
		}
	}		
	for(int f=0;f<k;f++)
		cout<<name[f]<<endl;
	return 0;
}
