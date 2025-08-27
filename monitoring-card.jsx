import React from 'react';
import { Card, CardContent, CardHeader, CardTitle } from './ui/card';
import { Button } from './ui/button';
import { Monitor, Video, Activity } from 'lucide-react';

export default function MonitoringSystemCard() {
  const handleOpenMonitoring = () => {
    // 監視システムのページに遷移
    window.open('/monitoring-system', '_blank');
  };

  return (
    <Card className="w-full max-w-sm hover:shadow-lg transition-shadow duration-300 cursor-pointer">
      <CardHeader className="pb-3">
        <div className="flex items-center space-x-2">
          <div className="p-2 bg-blue-100 rounded-lg">
            <Monitor className="h-6 w-6 text-blue-600" />
          </div>
          <CardTitle className="text-lg font-semibold">工場監視システム</CardTitle>
        </div>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="space-y-2">
          <div className="flex items-center space-x-2 text-sm text-gray-600">
            <Video className="h-4 w-4" />
            <span>CCTV監視・AI物体検出</span>
          </div>
          <div className="flex items-center space-x-2 text-sm text-gray-600">
            <Activity className="h-4 w-4" />
            <span>リアルタイム監視・録画</span>
          </div>
        </div>
        
        <div className="flex space-x-2">
          <Button 
            onClick={handleOpenMonitoring}
            className="flex-1 bg-blue-600 hover:bg-blue-700"
          >
            監視システムを開く
          </Button>
        </div>
        
        <div className="text-xs text-gray-500">
          最終更新: {new Date().toLocaleString('ja-JP')}
        </div>
      </CardContent>
    </Card>
  );
}
